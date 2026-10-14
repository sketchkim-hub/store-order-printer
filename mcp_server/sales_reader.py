# -*- coding: utf-8 -*-
"""영수증 프로그램 데이터 읽기 전용 모듈 (MCP 서버용).
- 파일은 읽기 모드로만 엽니다. 폴더 생성/파일 쓰기/queue·counter 접근 없음.
- 판매 CSV (sales/YYYY-MM-DD.csv, 품목마다 1행, 같은 주문은 같은 번호)를 기본으로 읽고,
  CSV 가 없으면 저널(sales/journal_YYYY-MM-DD.jsonl: 새 형식 items 배열 / 예전 1품목 형식)로 대체."""
import csv, datetime, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage import journal_read  # noqa: E402  (앱과 같은 저널 파서, 읽기 전용)

APP_NAME = "FestivalReceipt"
MAX_RANGE_DAYS = 366

class DataError(ValueError):
    pass

def resolve_data_dir(env=None):
    """앱과 같은 규칙으로 데이터 폴더를 찾되, 폴더를 만들지 않음.
    1) FESTIVAL_RECEIPT_DATA_DIR (또는 앱과 같은 FESTIVAL_RECEIPT_DATA)
    2) %APPDATA%\\FestivalReceipt
    3) ~/.FestivalReceipt"""
    env = os.environ if env is None else env
    for k in ("FESTIVAL_RECEIPT_DATA_DIR", "FESTIVAL_RECEIPT_DATA"):
        if env.get(k): return os.path.abspath(env[k])
    if env.get("APPDATA"): return os.path.join(env["APPDATA"], APP_NAME)
    return os.path.join(os.path.expanduser("~"), "." + APP_NAME)

def parse_date(s, name="date"):
    if not isinstance(s, str):
        raise DataError(f"{name}: 'YYYY-MM-DD' 형식 문자열이어야 합니다.")
    try:
        d = datetime.date.fromisoformat(s.strip())
    except ValueError:
        raise DataError(f"{name}: 날짜 형식이 잘못되었습니다 ('{s}'). 예: 2026-10-14")
    if len(s.strip()) != 10:
        raise DataError(f"{name}: 'YYYY-MM-DD' 형식으로 입력하세요 ('{s}').")
    return d

def _int(v):
    return int(str(v).replace(",", "").strip())

def read_day(base, day):
    """하루 판매 줄 목록: [{"order": 번호(str), "time", "name", "price", "qty", "amount"}], 건너뛴 줄 수, 출처"""
    ds = day.isoformat()
    sales = os.path.join(base, "sales")
    fn = os.path.join(sales, ds + ".csv")
    lines, skipped = [], 0
    if os.path.isfile(fn):
        with open(fn, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                try:
                    lines.append({"order": str(r["번호"]).strip(), "time": r.get("시각", ""), "name": r["품목"].strip(),
                                  "price": _int(r["단가"]), "qty": _int(r["수량"]), "amount": _int(r["금액"])})
                except (KeyError, ValueError, TypeError, AttributeError):
                    skipped += 1
        return lines, skipped, "csv"
    jf = os.path.join(sales, f"journal_{ds}.jsonl")
    if os.path.isfile(jf):
        for s in journal_read(jf):
            try:
                no = str(s["receipt_no"])
                items = s.get("items")
                if items is None:  # 예전 1품목 형식
                    items = [{"name": s["item"], "price": s["price"], "qty": s["qty"],
                              "amount": s.get("total", s["price"] * s["qty"])}]
                for it in items:
                    lines.append({"order": no, "time": s.get("time", ""), "name": it["name"], "price": _int(it["price"]),
                                  "qty": _int(it["qty"]), "amount": _int(it.get("amount", _int(it["price"]) * _int(it["qty"])))})
            except (KeyError, ValueError, TypeError):
                skipped += 1
        return lines, skipped, "journal"
    return [], 0, "none"

def summarize(lines):
    per = {}
    for l in lines:
        a = per.setdefault(l["name"], {"name": l["name"], "qty": 0, "amount": 0})
        a["qty"] += l["qty"]; a["amount"] += l["amount"]
    items = sorted(per.values(), key=lambda x: (-x["amount"], x["name"]))
    return {"total": sum(l["amount"] for l in lines), "order_count": len({l["order"] for l in lines}),
            "item_count": sum(l["qty"] for l in lines), "items": items}

def today_sales(base, today=None):
    day = today or datetime.date.today()
    lines, skipped, src = read_day(base, day)
    out = {"date": day.isoformat(), **summarize(lines), "source": src}
    if skipped: out["skipped_rows"] = skipped
    return out

def item_sales(base, start_date, end_date):
    s, e = parse_date(start_date, "start_date"), parse_date(end_date, "end_date")
    if s > e: raise DataError("start_date 가 end_date 보다 늦습니다.")
    if (e - s).days + 1 > MAX_RANGE_DAYS: raise DataError(f"기간은 최대 {MAX_RANGE_DAYS}일까지 조회할 수 있습니다.")
    all_lines, daily, skipped = [], [], 0
    d = s
    while d <= e:
        lines, sk, _ = read_day(base, d); skipped += sk
        if lines:
            sm = summarize(lines)
            daily.append({"date": d.isoformat(), "total": sm["total"], "order_count": sm["order_count"], "item_count": sm["item_count"]})
            # 날짜가 다르면 같은 영수증 번호도 다른 주문
            all_lines += [dict(l, order=f"{d.isoformat()}#{l['order']}") for l in lines]
        d += datetime.timedelta(days=1)
    sm = summarize(all_lines)
    out = {"start_date": s.isoformat(), "end_date": e.isoformat(), "total": sm["total"], "order_count": sm["order_count"],
           "item_count": sm["item_count"], "items": sm["items"], "daily": daily}
    if skipped: out["skipped_rows"] = skipped
    return out

def menu(base):
    fn = os.path.join(base, "menu.csv")
    if not os.path.isfile(fn): return {"items": [], "note": "menu.csv 가 없습니다 (프로그램 첫 설정 전)."}
    out = []
    with open(fn, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try: out.append({"key": _int(r["key"]), "name": r["name"].strip(), "price": _int(r["price"])})
            except (KeyError, ValueError, AttributeError): pass
    return {"items": out}
