# -*- coding: utf-8 -*-
"""떡축제 먹거리 영수증 프로그램 (SLK-TS100, ESC/POS, CP949)"""
import csv, json, os, sys, datetime, socket, unicodedata
from storage import atomic_write_json, journal_append
import firebase_sync
import printers as prn
import appconfig
from contextlib import contextmanager

BASE = appconfig.data_dir()   # 모든 데이터: %APPDATA%\FestivalReceipt (포터블이면 exe옆 data\)
P = lambda f: os.path.join(BASE, f)
WIDTH = 42  # 80mm, Font A = 42 cols (한글 1자 = 2칸)

@contextmanager
def paper_cols(pcfg):
    """프린터 용지 폭(58mm=32칸, 80mm=42칸)에 맞춰 영수증 폭 임시 변경"""
    global WIDTH
    old = WIDTH; WIDTH = appconfig.cols_for(pcfg)
    try: yield
    finally: WIDTH = old

def load_config():
    with open(P("config.json"), encoding="utf-8") as f:
        return appconfig.normalize_config(json.load(f))

def load_menu():
    if not os.path.exists(P("menu.csv")): appconfig.create_menu(BASE, sample=False)
    with open(P("menu.csv"), encoding="utf-8-sig") as f:
        return [dict(key=int(r["key"]), name=r["name"].strip(), price=int(r["price"])) for r in csv.DictReader(f)]

def w(s):  # 표시 폭 (East Asian Width: 한글/전각 = 2칸)
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)

def rj(s, n): return " " * max(0, n - w(s)) + s
def lj(s, n): return s + " " * max(0, n - w(s))

def lr(l, r):
    return l + " " * max(1, WIDTH - w(l) - w(r)) + r

def center(s):
    return " " * max(0, (WIDTH - w(s)) // 2) + s

def won(n):
    return f"{n:,}원"

def _counter():
    p = P("counter.json"); today = datetime.date.today().isoformat()
    d = {"date": today, "no": 0}
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f: d = json.load(f)
    return d if d.get("date") == today else {"date": today, "no": 0}

def peek_no():
    """다음 영수증 번호 (소모하지 않음)"""
    return _counter()["no"] + 1

def next_no():
    p = P("counter.json"); today = datetime.date.today().isoformat()
    d = {"date": today, "no": 0}
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f: d = json.load(f)
    if d.get("date") != today: d = {"date": today, "no": 0}
    d["no"] += 1
    atomic_write_json(p, d)
    return d["no"]

def to_order(item, qty=None):
    """주문(여러 줄) 정규화. item 이 dict 면 1줄 주문(예전 방식 호환), list 면 그대로.
    반환: [{key,name,price,qty,amount}] (수량 0 이하 줄 제외)"""
    src = item if isinstance(item, list) else [dict(item, qty=qty or 1)]
    out = []
    for it in src:
        q = int(it.get("qty", 1))
        if q > 0:
            out.append({"key": int(it.get("key", 0)), "name": it["name"], "price": int(it["price"]),
                        "qty": q, "amount": int(it["price"]) * q})
    return out

def order_total(order): return sum(l["amount"] for l in order)

def order_summary(order):
    s = ", ".join(f"{l['name']} x{l['qty']}" for l in order)
    return s if len(s) <= 40 else s[:38] + "…"

def build_receipt(cfg, item, qty, no, now=None):
    """item: 메뉴 dict(+qty) 또는 주문 list. 반환: (텍스트, 합계)"""
    now = now or datetime.datetime.now()
    order = to_order(item, qty); total = order_total(order)
    lines = [center(cfg["title"]), center(cfg.get("stall_name", "")), "-" * WIDTH,
             f"영수증 번호: {no:04d}", "일시: " + now.strftime("%Y-%m-%d %H:%M:%S"), "-" * WIDTH,
             lr("품목", rj("수량", 4) + rj("금액", 12))]
    for l in order:
        cols = rj(str(l["qty"]), 4) + rj(won(l["amount"]), 12)
        if w(l["name"]) > WIDTH - w(cols) - 1:  # 긴 이름은 별도 줄
            lines += [l["name"], rj(cols, WIDTH)]
        else:
            lines.append(lr(l["name"], cols))
    lines += ["-" * WIDTH, lr(f"합계 ({sum(l['qty'] for l in order)}개)", won(total)), "-" * WIDTH,
              center(cfg.get("footer", "")), ""]
    return "\n".join(lines), total

def to_escpos(text, cut=True, big_title=True):
    ESC, GS = b"\x1b", b"\x1d"
    out = ESC + b"@" + b"\x1c\x26"  # 초기화 + 한글(2바이트) 모드
    rows = text.split("\n")
    for i, line in enumerate(rows):
        data = line.encode("cp949", "replace") + b"\n"
        if big_title and i == 0:
            data = ESC + b"a\x01" + GS + b"!\x11" + line.strip().encode("cp949", "replace") + b"\n" + GS + b"!\x00" + ESC + b"a\x00"
        out += data
    out += b"\n" * 4
    if cut: out += GS + b"V\x42\x00"
    return out

def save_preview(text):
    os.makedirs(P("preview"), exist_ok=True)
    fn = P(os.path.join("preview", datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".txt"))
    with open(fn, "w", encoding="utf-8") as f: f.write(text)
    return fn

def print_raw(printer_name, data):
    import win32print
    h = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(h, 1, ("Receipt", None, "RAW"))
        win32print.StartPagePrinter(h); win32print.WritePrinter(h, data)
        win32print.EndPagePrinter(h); win32print.EndDocPrinter(h)
    finally:
        win32print.ClosePrinter(h)

class PrintError(Exception):
    pass

def friendly_error(e, name):
    code = getattr(e, "winerror", None) or (e.args[0] if getattr(e, "args", None) and isinstance(e.args[0], int) else None)
    if isinstance(e, ImportError):
        return "pywin32 가 설치되지 않았습니다. setup.bat 을 실행하세요."
    msgs = {1801: f"프린터 이름이 잘못되었습니다: '{name}'\nconfig.json 의 printer_name 을 Windows 프린터 이름과 똑같이 맞추세요.",
            1722: "인쇄 스풀러 서비스가 응답하지 않습니다. 컴퓨터를 다시 시작해 보세요.",
            5: "프린터 접근 권한이 없습니다.",
            1804: "프린터 드라이버/데이터 형식 오류입니다. 드라이버를 다시 설치하세요.",
            6: "프린터 연결이 끊어졌습니다(USB/전원 확인).", 31: "프린터가 응답하지 않습니다(USB/전원/용지 확인)."}
    return msgs.get(code, f"프린터 오류: {e}\n(USB 연결, 전원, 용지, printer_name 을 확인하세요)")

def check_printer_ready(name):
    import win32print
    h = win32print.OpenPrinter(name)
    try:
        st = win32print.GetPrinter(h, 2)
        attr, status = st["Attributes"], st["Status"]
    finally:
        win32print.ClosePrinter(h)
    if attr & 0x400: raise PrintError("프린터가 '오프라인'(USB 연결 끊김/전원 꺼짐) 상태입니다.")
    if status & 0x80: raise PrintError("프린터가 오프라인 상태입니다. 전원과 USB를 확인하세요.")
    if status & 0x10 or status & 0x40: raise PrintError("용지가 없거나 걸렸습니다.")
    if status & 0x1: raise PrintError("프린터가 일시 중지되었습니다. (프린터 대기열에서 '인쇄 계속')")
    if status & 0x2: raise PrintError("프린터 오류 상태입니다. 덮개/용지를 확인하세요.")

def try_print(cfg, text, printer=None, targets=None):
    """텍스트(테스트/매출요약)를 대상 프린터 모두에 출력. 하나라도 실패하면 프린터별 사유가 담긴 PrintError."""
    targets = targets if targets is not None else [p for p in prn.get_printers(cfg) if p["enabled"]]
    def make(p):
        if callable(text):
            with paper_cols(p): t = text()
        else: t = text
        lines = prn.text_to_lines(t); lines[0] = (lines[0][0].strip(), 1.4); return t, lines
    res = print_all(cfg, targets, make, printer)
    if any(e for _, e in res): raise PrintError(fail_report(res))
    return [p["label"] for p, _ in res]

def output(cfg, text, printer=None):
    """printer: 테스트용 대체 함수. 실패 시 미리보기 파일로 저장. 반환: 메시지"""
    data = to_escpos(text, cfg.get("cut_paper", True))
    if cfg.get("preview_only"):
        return "미리보기 저장: " + save_preview(text)
    try:
        try_print(cfg, text, printer)
        return "출력 완료"
    except Exception as e:
        return f"프린터 오류({e}) → 미리보기 저장: " + save_preview(text)

def log_sale(no, order, now=None):
    """CSV: 주문의 각 줄을 같은 번호로 한 행씩 (예전 형식과 동일한 열)."""
    now = now or datetime.datetime.now()
    os.makedirs(P("sales"), exist_ok=True)
    fn = P(os.path.join("sales", now.strftime("%Y-%m-%d") + ".csv"))
    new = not os.path.exists(fn)
    with open(fn, "a", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        if new: wr.writerow(["번호", "시각", "품목", "단가", "수량", "금액"])
        for l in order:
            wr.writerow([no, now.strftime("%H:%M:%S"), l["name"], l["price"], l["qty"], l["amount"]])
        f.flush(); os.fsync(f.fileno())

def daily_summary(cfg, date=None):
    date = date or datetime.date.today().isoformat()
    fn = P(os.path.join("sales", date + ".csv"))
    agg, receipts = {}, set()
    if os.path.exists(fn):
        with open(fn, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):  # 예전(1품목) / 새(여러 품목) 기록 모두 같은 행 형식
                a = agg.setdefault(r["품목"], [0, 0]); a[0] += int(r["수량"]); a[1] += int(r["금액"])
                receipts.add(r["번호"])
    lines = [center(cfg["title"]), center(f"일일 매출 ({date})"), "-" * WIDTH]
    for k, (q, t) in agg.items(): lines.append(lr(f"{k} x{q}", won(t)))
    lines += ["-" * WIDTH, lr(f"영수증 {len(receipts)}건 / {sum(v[0] for v in agg.values())}개",
                              won(sum(v[1] for v in agg.values()))), ""]
    return "\n".join(lines)

def device_id(cfg):
    return "".join(c for c in (cfg.get("device_id") or socket.gethostname()) if c.isalnum() or c in "-_")[:30] or "pc"

def backup_dir(cfg):
    d = cfg.get("backup_dir") or "backup"
    return d if os.path.isabs(d) else P(d)

def make_sale(cfg, order, no, now):
    return {"sale_id": f"{now:%Y%m%d}-{no:04d}-{device_id(cfg)}", "date": f"{now:%Y-%m-%d}",
            "time": f"{now:%H:%M:%S}", "receipt_no": no, "device_id": device_id(cfg),
            "items": order, "total": order_total(order)}

def backup_sale(cfg, sale):
    """백업: 추가전용 저널(fsync) + 판매별 개별 파일(원자적). 백업 실패해도 판매는 계속."""
    try:
        d = backup_dir(cfg)
        journal_append(os.path.join(d, f"journal_{sale['date']}.jsonl"), sale)
        atomic_write_json(os.path.join(d, sale["date"], sale["sale_id"] + ".json"), sale)
        return True
    except Exception:
        return False

SYNC = None  # firebase_sync.SyncWorker

def record_sale(cfg, item, qty, now=None):
    """번호 소모 + 저널/백업/큐/CSV 기록. (no, text, backup_ok) 반환"""
    now = now or datetime.datetime.now()
    no = next_no()
    order = to_order(item, qty)
    if not order: raise ValueError("빈 주문")
    text, total = build_receipt(cfg, order, None, no, now)
    sale = make_sale(cfg, order, no, now)
    journal_append(P(os.path.join("sales", f"journal_{sale['date']}.jsonl")), sale)
    ok = backup_sale(cfg, sale)
    if SYNC: SYNC.enqueue(sale)
    log_sale(no, order, now)
    return no, text, ok

def render_for(cfg, pcfg, item, qty, no, now=None):
    """프린터별 출력 내용. 반환: (미리보기 텍스트, 줄목록[(text, scale)])"""
    with paper_cols(pcfg):
        return _render_for(cfg, pcfg, item, qty, no, now)

def _render_for(cfg, pcfg, item, qty, no, now=None):
    if pcfg.get("layout") == "label":
        lines = prn.build_label(cfg, to_order(item, qty), None, no, now)
        return "\n".join(center(t) for t, _ in lines) + "\n", lines
    t, _ = build_receipt(cfg, item, qty, no, now)
    lines = prn.text_to_lines(t); lines[0] = (lines[0][0].strip(), 1.6)
    return t, lines

def send_to(cfg, pcfg, text, lines, printer=None):
    """한 프린터로 출력. 실패 시 PrintError."""
    try:
        if pcfg.get("mode") == "gdi":
            if printer: printer(pcfg["name"], lines)
            else: prn.print_gdi(pcfg, lines)
        else:
            data = to_escpos(text, cfg.get("cut_paper", True))
            if printer: printer(pcfg["name"], data)
            else: check_printer_ready(pcfg["name"]); print_raw(pcfg["name"], data)
    except PrintError: raise
    except Exception as e:
        raise PrintError(friendly_error(e, pcfg["name"]))

def print_all(cfg, targets, make, printer=None):
    """targets 각각 출력. make(pcfg)->(text, lines). 반환: [(pcfg, None|오류메시지)]"""
    res = []
    for p in targets:
        try:
            t, l = make(p); send_to(cfg, p, t, l, printer); res.append((p, None))
        except PrintError as e:
            res.append((p, str(e)))
    return res

def fail_report(res):
    return "\n\n".join(f"[{p['label']}] {err}" for p, err in res if err)

def confirm_sale(cfg, item, qty, printer=None, on_fail=None, now=None, targets=None):
    """미리보기 [인쇄]. 한 대라도 성공 → 기록(실패 프린터는 경고). 모두 실패 → on_fail(메시지) True 면 미리보기 저장 후 기록.
    반환: (recorded, 상태메시지)"""
    now = now or datetime.datetime.now()
    targets = targets if targets is not None else [p for p in prn.get_printers(cfg) if p["enabled"]]
    no = peek_no()
    if cfg.get("preview_only") or not targets:
        no, text, ok = record_sale(cfg, item, qty, now)
        return True, f"#{no:04d} 미리보기 저장: " + save_preview(text) + ("" if ok else " / ⚠백업 실패")
    res = print_all(cfg, targets, lambda p: render_for(cfg, p, item, qty, no, now), printer)
    good = [p["label"] for p, e in res if not e]
    if not good:
        if on_fail and on_fail(fail_report(res)):
            no, text, ok = record_sale(cfg, item, qty, now)
            return True, f"#{no:04d} 인쇄 실패 → 미리보기 저장: " + save_preview(text) + ("" if ok else " / ⚠백업 실패")
        return False, "인쇄 실패 - 판매 기록 안 함"
    no, _, ok = record_sale(cfg, item, qty, now)
    msg = f"#{no:04d} {order_summary(to_order(item, qty))} 출력 완료({', '.join(good)})" + ("" if ok else " / ⚠백업 실패")
    if len(good) < len(res):
        msg += " / ⚠일부 실패: " + ", ".join(p["label"] for p, e in res if e)
        if on_fail is not None and hasattr(on_fail, "warn"): on_fail.warn(fail_report(res))
    return True, msg

def sell(cfg, item, qty=1, printer=None, now=None):
    """미리보기 없이 바로 출력 + 기록 (출력 실패해도 기록, 미리보기 파일 저장)."""
    no, text, ok = record_sale(cfg, item, qty, now)
    msg = output(cfg, text, printer)
    return no, text, msg + ("" if ok else " / ⚠백업 실패")

def validate_menu(rows):
    """rows=[(name, price)] → (정규화된 메뉴, 오류목록). 키는 1부터 다시 매김."""
    errs, out = [], []
    for i, (name, price) in enumerate(rows, 1):
        name = str(name).strip(); ps = str(price).replace(",", "").replace("원", "").strip()
        if not name: errs.append(f"{i}번: 품목 이름이 비어 있습니다.")
        if not ps.isdigit() or int(ps) <= 0: errs.append(f"{i}번: 가격은 0보다 큰 정수여야 합니다. ('{price}')")
        out.append({"key": i, "name": name, "price": int(ps) if ps.isdigit() else 0})
    if not rows: errs.append("메뉴가 최소 1개는 있어야 합니다.")
    return out, errs

def save_menu(menu):
    """menu.csv 원자적 저장 + 시간 표시 백업(menu.csv.bak_YYYYmmdd_HHMMSS)."""
    import io, shutil
    p = P("menu.csv")
    if os.path.exists(p):
        shutil.copy2(p, p + ".bak_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    buf = io.StringIO(); wr = csv.writer(buf, lineterminator="\n")
    wr.writerow(["key", "name", "price"])
    for m in menu: wr.writerow([m["key"], m["name"], m["price"]])
    from storage import atomic_write
    atomic_write(p, buf.getvalue())

# ---- 관리자 PIN (4자리, admin.json 에 솔트+PBKDF2 해시로만 저장) ----
import hashlib, hmac, time as _time
PIN_ITER, MAX_TRIES, LOCK_SEC = 200_000, 5, 60
_pin_state = {"fails": 0, "locked_until": 0.0}

def pin_valid_format(pin): return isinstance(pin, str) and len(pin) == 4 and pin.isdigit()

def _admin_path(): return P("admin.json")

def pin_is_set(): return os.path.exists(_admin_path())

def set_pin(pin):
    if not pin_valid_format(pin): raise ValueError("PIN 은 숫자 4자리여야 합니다.")
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, PIN_ITER)
    atomic_write_json(_admin_path(), {"algo": "pbkdf2_sha256", "iter": PIN_ITER, "salt": salt.hex(), "hash": h.hex()})

def verify_pin(pin, now=None):
    """반환: (성공여부, 메시지). 5회 틀리면 60초 잠금."""
    now = now if now is not None else _time.time()
    if now < _pin_state["locked_until"]:
        return False, f"잠김: {int(_pin_state['locked_until'] - now) + 1}초 후 다시 시도하세요."
    with open(_admin_path(), encoding="utf-8") as f: a = json.load(f)
    h = hashlib.pbkdf2_hmac("sha256", str(pin).encode(), bytes.fromhex(a["salt"]), int(a["iter"]))
    if pin_valid_format(str(pin)) and hmac.compare_digest(h.hex(), a["hash"]):
        _pin_state["fails"] = 0; return True, "OK"
    _pin_state["fails"] += 1
    if _pin_state["fails"] >= MAX_TRIES:
        _pin_state["fails"] = 0; _pin_state["locked_until"] = now + LOCK_SEC
        return False, f"PIN 이 {MAX_TRIES}회 틀려 {LOCK_SEC}초 동안 잠깁니다."
    return False, f"PIN 이 틀렸습니다. ({_pin_state['fails']}/{MAX_TRIES})"

def key_hint(k):
    if k <= 9: return str(k)
    if k == 10: return "0"
    if k <= 12: return f"F{k}"
    if k <= 14: return f"Shift+F{k - 12}"
    return ""

def test_receipt_text(cfg):
    return "\n".join([center(cfg.get("title", "") or "테스트"), center("테스트 인쇄"), "-" * WIDTH,
                      center("한글 출력 확인 가나다 123"),
                      lr("품목", rj("수량", 4) + rj("금액", 12)), lr("떡볶이", rj("1", 4) + rj(won(4000), 12)),
                      "-" * WIDTH, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ""])

def test_print_one(pcfg, cfg, printer=None):
    """설정 창/마법사의 프린터별 테스트 인쇄. 성공 메시지 반환, 실패 시 PrintError."""
    pcfg = appconfig.normalize_printer(pcfg)
    if not pcfg["name"]: raise PrintError("프린터를 먼저 선택하세요.")
    with paper_cols(pcfg):
        t = test_receipt_text(cfg)
    lines = prn.text_to_lines(t); lines[0] = (lines[0][0].strip(), 1.4)
    send_to(cfg, pcfg, t, lines, printer)
    return f"'{pcfg['name']}' 테스트 인쇄를 보냈습니다. 한글이 바르게 나왔는지 확인하세요."

class Cart:
    """장바구니: 같은 메뉴를 다시 누르면 수량 증가. 줄 순서 = 처음 담은 순서."""
    MAX_QTY, MAX_LINES = 999, 50
    def __init__(self): self.lines = []
    def add(self, item, n=1):
        for i, l in enumerate(self.lines):
            if l["key"] == item["key"] and l["name"] == item["name"]:
                l["qty"] = min(self.MAX_QTY, l["qty"] + n); return i
        if len(self.lines) >= self.MAX_LINES: raise ValueError(f"한 주문은 최대 {self.MAX_LINES}개 품목까지 가능합니다.")
        self.lines.append({"key": item["key"], "name": item["name"], "price": item["price"], "qty": min(self.MAX_QTY, n)})
        return len(self.lines) - 1
    def change(self, i, d):
        """수량 ±d. 0 이 되면 줄 삭제. 반환: 남은 줄 인덱스(삭제되면 None)"""
        if not 0 <= i < len(self.lines): return None
        self.lines[i]["qty"] = min(self.MAX_QTY, self.lines[i]["qty"] + d)
        if self.lines[i]["qty"] <= 0: self.lines.pop(i); return None
        return i
    def remove(self, i):
        if 0 <= i < len(self.lines): self.lines.pop(i)
    def clear(self): self.lines = []
    def order(self): return to_order([dict(l) for l in self.lines])
    def total(self): return order_total(self.order())
    def count(self): return sum(l["qty"] for l in self.lines)
    def __len__(self): return len(self.lines)

# ---------------- GUI ----------------
MONO = ("D2Coding", "GulimChe", "굴림체", "돋움체", "Courier New")

def mono_font(tk, size=12):
    from tkinter import font
    fams = set(font.families())
    for f in MONO:
        if f in fams: return (f, size)
    return ("TkFixedFont", size)

def preview_dialog(root, cfg, title, render, on_print, qty_init=None):
    """모달 미리보기. render(qty)->text. on_print(qty)->닫을지 여부. qty_init=None 이면 수량 조절 없음."""
    import tkinter as tk
    win = tk.Toplevel(root); win.title(title); win.transient(root); win.grab_set(); win.configure(bg="#888")
    qty = tk.IntVar(value=qty_init or 1)
    paper = tk.Text(win, width=WIDTH + 2, height=20, font=mono_font(tk, 13), bg="white", fg="black",
                    relief="flat", padx=12, pady=12)
    paper.pack(padx=20, pady=(20, 10))
    def refresh():
        t = render(qty.get())
        paper.config(state="normal"); paper.delete("1.0", "end"); paper.insert("1.0", t)
        paper.config(height=t.count("\n") + 2, state="disabled")
    bar = tk.Frame(win, bg="#888"); bar.pack(pady=(0, 15))
    if qty_init is not None:
        def chg(d): qty.set(max(1, min(999, qty.get() + d))); refresh()
        tk.Button(bar, text="－", font=("맑은 고딕", 16), width=3, command=lambda: chg(-1)).pack(side="left")
        tk.Label(bar, textvariable=qty, font=("맑은 고딕", 18, "bold"), width=4).pack(side="left")
        tk.Button(bar, text="＋", font=("맑은 고딕", 16), width=3, command=lambda: chg(1)).pack(side="left", padx=(0, 20))
        win.bind("<plus>", lambda e: chg(1)); win.bind("<KP_Add>", lambda e: chg(1))
        win.bind("<minus>", lambda e: chg(-1)); win.bind("<KP_Subtract>", lambda e: chg(-1))
    def do_print(e=None):
        if on_print(qty.get()): win.destroy()
    tk.Button(bar, text="인쇄 (Enter)", font=("맑은 고딕", 16, "bold"), bg="#4caf50", fg="white", command=do_print).pack(side="left", padx=5)
    tk.Button(bar, text="취소 (Esc)", font=("맑은 고딕", 16), command=win.destroy).pack(side="left", padx=5)
    win.bind("<Return>", do_print); win.bind("<KP_Enter>", do_print); win.bind("<Escape>", lambda e: win.destroy())
    refresh(); win.focus_force(); root.wait_window(win)

def main():
    global SYNC
    import tkinter as tk
    from tkinter import messagebox
    import settings_ui
    root = tk.Tk(); root.title("영수증")
    try: root.iconbitmap(os.path.join(appconfig.resource_dir(), "app.ico"))
    except Exception: pass
    first_menu = None
    migrated = appconfig.migrate_legacy(BASE)  # 예전 버전 데이터 자동 이전
    if appconfig.is_first_run(BASE):
        root.withdraw()
        first_menu = settings_ui.first_run_wizard(root, BASE, test_print_one, set_pin, pin_valid_format)
        if first_menu is None: root.destroy(); return
        root.deiconify()
    cfg, menu = load_config(), load_menu()
    root.title(cfg["title"] + " 영수증")
    def make_fb():
        try:
            fc = firebase_sync.load_firebase_config(BASE)
            return firebase_sync.FirestoreClient(fc) if fc else None
        except Exception: return None
    SYNC = firebase_sync.SyncWorker(BASE, make_fb()); SYNC.start()
    if os.name == "nt": root.state("zoomed")
    qty = tk.IntVar(value=1)  # 한 번 누를 때 담는 수량
    cart = Cart()
    status = tk.StringVar(value="메뉴키(1~9,0,F1~F12,Shift+F1/F2)로 담기 → Enter 결제/인쇄 · +/- 선택줄 수량 · Delete 줄삭제 · Esc 전체취소")
    busy = [False]
    plist = prn.get_printers(cfg)
    pvars = [tk.BooleanVar(value=bool(p["enabled"])) for p in plist]
    def targets(): return [p for p, v in zip(plist, pvars) if v.get()]
    def tdesc(p):
        pp = p.get("paper", "auto")
        return f"{p['label']} ({'영수증' if p['mode'] == 'escpos' else '드라이버'}/{'라벨' if p['layout'] == 'label' else '전체'}" + (f", {pp}mm" if pp != "auto" else "") + ")"
    def with_targets(render):
        def r(q):
            ts = targets()
            if not ts: return "※ 선택된 프린터 없음 → 미리보기 파일로만 저장됩니다\n\n" + render(q, None)
            def one(p):
                with paper_cols(p): return render(q, p)
            if len(ts) == 1: return "▶ " + tdesc(ts[0]) + "\n\n" + one(ts[0])
            return "\n".join("▶ " + tdesc(p) + "\n" + one(p) for p in ts)
        return r

    def ask_fail(msg):
        return messagebox.askyesno("인쇄 실패", msg + "\n\n영수증을 미리보기 텍스트로 저장하고 판매를 기록할까요?\n(아니오 = 기록하지 않음)", icon="error")

    def finish(order):
        def warn(m): messagebox.showwarning("일부 프린터 인쇄 실패", m + "\n\n판매는 기록되었습니다 (다른 프린터는 출력 성공).")
        ask_fail.warn = warn
        rec, msg = confirm_sale(cfg, order, None, on_fail=ask_fail, targets=targets())
        status.set(msg)
        if rec: cart.clear(); qty.set(1); redraw_cart()
        return True

    def do(item):
        """메뉴 키/버튼: 장바구니에 담기 (다시 누르면 수량 증가)"""
        if busy[0]: return
        try: i = cart.add(item, qty.get())
        except ValueError as e: messagebox.showwarning("장바구니", str(e)); return
        redraw_cart(i)

    def checkout(e=None):
        if busy[0]: return
        if not len(cart): status.set("장바구니가 비어 있습니다."); return
        busy[0] = True
        try:
            order = cart.order()
            if cfg.get("show_preview", True):
                preview_dialog(root, cfg, f"결제 미리보기 - {won(order_total(order))}",
                               with_targets(lambda q, p: render_for(cfg, p or {}, order, None, peek_no())[0]),
                               lambda q: finish(order))
            else:
                finish(order)
        finally:
            busy[0] = False

    def clear_cart(e=None):
        if busy[0] or not len(cart): return
        if messagebox.askyesno("전체 취소", f"장바구니 {cart.count()}개 ({won(cart.total())})를 모두 비울까요?"):
            cart.clear(); redraw_cart(); status.set("장바구니를 비웠습니다.")

    def test_text(q=1):
        return "\n".join([center("테스트 인쇄"), "-" * WIDTH, center("한글 출력 확인 가나다 123"),
                          lr("품목", rj("수량", 4) + rj("금액", 12)), lr("닭꼬치", rj("1", 4) + rj(won(4000), 12)),
                          "-" * WIDTH, center("프린터 출력 확인"),
                          datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ""])

    def test_print():
        def go(q):
            try:
                if cfg.get("preview_only"): status.set("미리보기 저장: " + save_preview(test_text()))
                else: status.set("테스트 인쇄 완료: " + ", ".join(try_print(cfg, test_text, targets=targets())))
            except PrintError as e:
                if messagebox.askyesno("테스트 인쇄 실패", str(e) + "\n\n미리보기 텍스트로 저장할까요?", icon="error"):
                    status.set("미리보기 저장: " + save_preview(test_text()))
                else: status.set("테스트 인쇄 실패")
            return True
        preview_dialog(root, cfg, "테스트 인쇄 미리보기", with_targets(lambda q, p: test_text()), go)

    def summary_print():
        def go(q):
            try:
                if cfg.get("preview_only"): status.set("미리보기 저장: " + save_preview(daily_summary(cfg)))
                else: try_print(cfg, lambda: daily_summary(cfg), targets=targets()); status.set("매출 요약 인쇄 완료")
            except PrintError as e:
                if messagebox.askyesno("인쇄 실패", str(e) + "\n\n미리보기 텍스트로 저장할까요?", icon="error"):
                    status.set("미리보기 저장: " + save_preview(daily_summary(cfg)))
            return True
        preview_dialog(root, cfg, "오늘 매출 미리보기", with_targets(lambda q, p: daily_summary(cfg)), go)

    top = tk.Frame(root); top.pack(fill="x", pady=5)
    tk.Label(top, text="담는 수량:", font=("맑은 고딕", 16)).pack(side="left", padx=10)
    tk.Button(top, text="-", font=("맑은 고딕", 18), width=3, command=lambda: qty.set(max(1, qty.get() - 1))).pack(side="left")
    tk.Label(top, textvariable=qty, font=("맑은 고딕", 22, "bold"), width=3).pack(side="left")
    tk.Button(top, text="+", font=("맑은 고딕", 18), width=3, command=lambda: qty.set(qty.get() + 1)).pack(side="left")
    tk.Button(top, text="설정", font=("맑은 고딕", 14), command=lambda: open_settings()).pack(side="right", padx=5)
    tk.Button(top, text="메뉴 관리", font=("맑은 고딕", 14), command=lambda: menu_editor()).pack(side="right", padx=5)
    tk.Button(top, text="테스트 인쇄", font=("맑은 고딕", 14), command=test_print).pack(side="right", padx=5)
    tk.Button(top, text="오늘 매출 출력", font=("맑은 고딕", 14), command=summary_print).pack(side="right", padx=5)
    pf = tk.Frame(root); pf.pack(fill="x", padx=10)
    def build_printer_bar():
        for wdg in pf.winfo_children(): wdg.destroy()
        tk.Label(pf, text="출력 프린터:", font=("맑은 고딕", 13)).pack(side="left")
        if not plist: tk.Label(pf, text="없음 → [설정]에서 프린터를 추가하세요 (지금은 미리보기 파일로 저장)", fg="red", font=("맑은 고딕", 13)).pack(side="left")
        for p, v in zip(plist, pvars):
            tk.Checkbutton(pf, text=tdesc(p), variable=v, font=("맑은 고딕", 13), takefocus=0).pack(side="left", padx=8)
    build_printer_bar()

    def open_settings():
        if busy[0] or not require_pin("설정"): return
        def saved(new, fb_changed):
            cfg.clear(); cfg.update(new)
            plist[:] = prn.get_printers(cfg)
            pvars[:] = [tk.BooleanVar(value=bool(p["enabled"])) for p in plist]
            build_printer_bar(); root.title(cfg["title"] + " 영수증")
            if fb_changed: SYNC.client = make_fb(); SYNC.offline = False; SYNC.ev.set()
            status.set("설정을 저장했습니다.")
        settings_ui.settings_window(root, cfg, BASE, saved, test_print_one)
    body = tk.Frame(root); body.pack(fill="both", expand=True)
    cp = tk.Frame(body, bd=2, relief="groove"); cp.pack(side="right", fill="y", padx=5, pady=5)
    grid = tk.Frame(body); grid.pack(side="left", fill="both", expand=True, padx=5, pady=5)
    from tkinter import ttk
    ttk.Style().configure("Cart.Treeview", font=("맑은 고딕", 14), rowheight=32)
    ttk.Style().configure("Cart.Treeview.Heading", font=("맑은 고딕", 12, "bold"))
    tk.Label(cp, text="주문 내역", font=("맑은 고딕", 16, "bold")).pack(pady=(5, 0))
    ctv = ttk.Treeview(cp, columns=("n", "q", "a"), show="headings", height=12, selectmode="browse", style="Cart.Treeview")
    for c, t, wd, an in (("n", "품목", 190, "w"), ("q", "수량", 60, "center"), ("a", "금액", 110, "e")):
        ctv.heading(c, text=t); ctv.column(c, width=wd, anchor=an)
    ctv.pack(fill="both", expand=True, padx=5, pady=5)
    lb = tk.Frame(cp); lb.pack()
    def sel():
        s_ = ctv.selection(); return int(s_[0]) if s_ else None
    def line_chg(d):
        i = sel()
        if i is None and len(cart): i = len(cart) - 1
        if i is None: return
        r = cart.change(i, d); redraw_cart(r if r is not None else min(i, len(cart) - 1))
    def line_del():
        i = sel()
        if i is not None: cart.remove(i); redraw_cart(min(i, len(cart) - 1))
    for t, c in (("－", lambda: line_chg(-1)), ("＋", lambda: line_chg(1)), ("줄 삭제", line_del)):
        tk.Button(lb, text=t, font=("맑은 고딕", 14), width=6 if len(t) > 1 else 3, takefocus=0, command=c).pack(side="left", padx=3)
    totvar = tk.StringVar(value="합계 0원")
    tk.Label(cp, textvariable=totvar, font=("맑은 고딕", 28, "bold"), fg="#c62828").pack(pady=8)
    tk.Button(cp, text="결제 / 인쇄 (Enter)", font=("맑은 고딕", 20, "bold"), bg="#4caf50", fg="white",
              takefocus=0, command=checkout).pack(fill="x", padx=8, pady=4)
    tk.Button(cp, text="전체 취소 (Esc)", font=("맑은 고딕", 14), takefocus=0, command=clear_cart).pack(fill="x", padx=8, pady=(0, 8))
    def redraw_cart(select=None):
        ctv.delete(*ctv.get_children())
        for i, l in enumerate(cart.order()):
            ctv.insert("", "end", iid=str(i), values=(l["name"], l["qty"], won(l["amount"])))
        if select is not None and 0 <= select < len(cart):
            ctv.selection_set(str(select)); ctv.see(str(select))
        totvar.set(f"합계 {won(cart.total())}" + (f"  ({cart.count()}개)" if len(cart) else ""))
    def onroot(f): return lambda e: f() if e.widget.winfo_toplevel() is root else None
    for seq in ("<plus>", "<KP_Add>", "<equal>"): root.bind(seq, onroot(lambda: line_chg(1)))
    for seq in ("<minus>", "<KP_Subtract>"): root.bind(seq, onroot(lambda: line_chg(-1)))
    root.bind("<Delete>", onroot(line_del))
    for seq in ("<Return>", "<KP_Enter>"): root.bind(seq, onroot(checkout))
    for seq in ("<Escape>", "<BackSpace>"): root.bind(seq, onroot(clear_cart))
    by = {}
    def build_grid():
        for wdg in grid.winfo_children(): wdg.destroy()
        for c in range(8): grid.columnconfigure(c, weight=0); grid.rowconfigure(c, weight=0)
        by.clear(); by.update({it["key"]: it for it in menu})
        for i, it in enumerate(menu):
            h = key_hint(it["key"])
            tk.Button(grid, text=(f"[{h}] " if h else "") + f"{it['name']}\n{won(it['price'])}", font=("맑은 고딕", 16, "bold"),
                      bg="#ffe680", command=lambda it=it: do(it)).grid(row=i // 4, column=i % 4, sticky="nsew", padx=4, pady=4)
        for c in range(4): grid.columnconfigure(c, weight=1)
        for r in range((len(menu) + 3) // 4): grid.rowconfigure(r, weight=1)
    build_grid()
    def bind(seq, k):
        root.bind(seq, lambda e: do(by[k]) if k in by and e.widget.winfo_toplevel() is root else None)
    for k in range(1, 10): bind(str(k), k); bind(f"<KP_{k}>", k)
    bind("0", 10); bind("<KP_0>", 10)
    for k in range(1, 13): bind(f"<F{k}>", k)
    bind("<Shift-F1>", 13); bind("<Shift-F2>", 14)

    def new_pin_dialog(parent, msg):
        from tkinter import simpledialog
        while True:
            p1 = simpledialog.askstring("PIN 설정", msg + "\n새 PIN (숫자 4자리):", show="*", parent=parent)
            if p1 is None: return False
            if not pin_valid_format(p1): messagebox.showerror("PIN 설정", "숫자 4자리로 입력하세요.", parent=parent); continue
            p2 = simpledialog.askstring("PIN 설정", "한 번 더 입력하세요:", show="*", parent=parent)
            if p2 is None: return False
            if p1 != p2: messagebox.showerror("PIN 설정", "두 PIN 이 다릅니다. 다시 입력하세요.", parent=parent); continue
            set_pin(p1); messagebox.showinfo("PIN 설정", "PIN 이 저장되었습니다.", parent=parent); return True

    def change_pin(parent):
        from tkinter import simpledialog
        p = simpledialog.askstring("PIN 변경", "현재 PIN:", show="*", parent=parent)
        if p is None: return
        ok, m = verify_pin(p)
        if not ok: messagebox.showerror("PIN 변경", m, parent=parent); return
        new_pin_dialog(parent, "새 PIN 을 설정합니다.")

    def require_pin(title):
        from tkinter import simpledialog
        if not pin_is_set():
            return new_pin_dialog(root, f"처음 사용: 관리자 PIN(숫자 4자리)을 설정하세요.")
        p = simpledialog.askstring(title, "관리자 PIN (숫자 4자리):", show="*", parent=root)
        if p is None: return False
        ok, m = verify_pin(p)
        if not ok: messagebox.showerror(title, m, parent=root)
        return ok

    def menu_editor(skip_pin=False):
        from tkinter import simpledialog, ttk
        if not skip_pin and not require_pin("메뉴 관리"): return
        win = tk.Toplevel(root); win.title("메뉴 관리"); win.transient(root); win.grab_set()
        tv = ttk.Treeview(win, columns=("k", "n", "p"), show="headings", height=16, selectmode="browse")
        for c, t, wd in (("k", "번호(단축키)", 110), ("n", "품목", 260), ("p", "가격", 110)):
            tv.heading(c, text=t); tv.column(c, width=wd, anchor="e" if c == "p" else "w")
        tv.grid(row=0, column=0, columnspan=6, padx=10, pady=10, sticky="nsew")
        st = ttk.Style(); st.configure("Treeview", font=("맑은 고딕", 13), rowheight=28)
        rows = [[m["name"], str(m["price"])] for m in menu]
        def redraw(sel=None):
            tv.delete(*tv.get_children())
            for i, (n, p) in enumerate(rows, 1):
                h = key_hint(i); tv.insert("", "end", iid=str(i - 1), values=(f"{i} ({h})" if h else str(i), n, p))
            if sel is not None and 0 <= sel < len(rows): tv.selection_set(str(sel)); tv.see(str(sel)); load(sel)
        nv, pv = tk.StringVar(), tk.StringVar()
        def cur():
            s_ = tv.selection(); return int(s_[0]) if s_ else None
        def load(i):
            nv.set(rows[i][0]); pv.set(rows[i][1])
        tv.bind("<<TreeviewSelect>>", lambda e: cur() is not None and load(cur()))
        tk.Label(win, text="품목", font=("맑은 고딕", 12)).grid(row=1, column=0, sticky="e")
        name_entry = tk.Entry(win, textvariable=nv, font=("맑은 고딕", 13), width=18)
        name_entry.grid(row=1, column=1, columnspan=2, sticky="w")
        tk.Label(win, text="가격", font=("맑은 고딕", 12)).grid(row=1, column=3, sticky="e")
        tk.Entry(win, textvariable=pv, font=("맑은 고딕", 13), width=9).grid(row=1, column=4, sticky="w")
        orig = [list(r) for r in rows]
        def pending():  # 입력칸에 적용 안 한 수정이 있는지
            i = cur()
            return i is not None and [nv.get(), pv.get()] != rows[i]
        def dirty(): return rows != orig or pending()
        def mark(*_):
            win.title("메뉴 관리" + ("  ● 저장 안 된 변경 있음" if dirty() else ""))
        nv.trace_add("write", mark); pv.trace_add("write", mark)
        def apply():
            i = cur()
            if i is None: return
            rows[i] = [nv.get(), pv.get()]; redraw(i); mark()
        def add():
            rows.append(["새 메뉴", "1000"]); redraw(len(rows) - 1); mark()
            name_entry.focus_set(); name_entry.select_range(0, "end")
        def delete():
            i = cur()
            if i is not None and messagebox.askyesno("삭제", f"'{rows[i][0]}' 을(를) 삭제할까요?", parent=win):
                rows.pop(i); redraw(min(i, len(rows) - 1)); mark()
        def move(d):
            i = cur()
            if i is None or not 0 <= i + d < len(rows): return
            if pending(): rows[i] = [nv.get(), pv.get()]
            rows[i], rows[i + d] = rows[i + d], rows[i]; redraw(i + d); mark()
        def save():
            if pending(): rows[cur()] = [nv.get(), pv.get()]  # 입력칸 수정도 자동 반영
            new, errs = validate_menu(rows)
            if errs: messagebox.showerror("입력 오류", "\n".join(errs), parent=win); return False
            try: save_menu(new)
            except Exception as e: messagebox.showerror("저장 실패", str(e), parent=win); return False
            menu[:] = new; build_grid(); status.set(f"메뉴 저장 완료 ({len(new)}개)"); win.destroy(); return True
        def close(e=None):
            if dirty():
                ans = messagebox.askyesnocancel("메뉴 관리", "변경한 메뉴를 저장할까요?\n\n예 = 저장 후 닫기 / 아니오 = 버리고 닫기 / 취소 = 계속 편집", parent=win)
                if ans is None: return
                if ans: save(); return
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", close)
        bf = tk.Frame(win); bf.grid(row=2, column=0, columnspan=6, pady=10)
        for t, c in (("수정 적용", apply), ("추가", add), ("삭제", delete), ("▲ 위로", lambda: move(-1)),
                     ("▼ 아래로", lambda: move(1)), ("PIN 변경", lambda: change_pin(win)), ("닫기", close)):
            tk.Button(bf, text=t, font=("맑은 고딕", 12), width=8, command=c).pack(side="left", padx=3)
        tk.Button(win, text="저장 (적용)", font=("맑은 고딕", 16, "bold"), bg="#4caf50", fg="white",
                  activebackground="#388e3c", command=save).grid(row=3, column=0, columnspan=6, sticky="ew", padx=10, pady=(0, 10))
        win.bind("<Escape>", close)
        redraw(0 if rows else None); mark()
    tk.Label(root, textvariable=status, font=("맑은 고딕", 14), fg="blue").pack(fill="x", pady=5)
    fbvar = tk.StringVar(); fblbl = tk.Label(root, textvariable=fbvar, font=("맑은 고딕", 13)); fblbl.pack(fill="x")
    def refresh():
        st, n = SYNC.status()
        txt, col = {"disabled": ("Firebase: 사용 안 함 (오프라인 모드)", "gray"), "synced": ("Firebase: ✔ 동기화 완료", "green"),
                    "waiting": (f"Firebase: 전송 대기 {n}건", "orange"), "offline": (f"Firebase: ✖ 오프라인 - 대기 {n}건", "red")}[st]
        fbvar.set(txt); fblbl.config(fg=col); root.after(2000, refresh)
    refresh()
    if first_menu == "blank" or not menu:
        root.after(300, lambda: menu_editor(skip_pin=(first_menu == "blank")))
    root.mainloop()

if __name__ == "__main__":
    main()
