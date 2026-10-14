# -*- coding: utf-8 -*-
"""설정 창 / 첫 실행 마법사 (JSON 직접 편집 불필요)"""
import copy, json, os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import appconfig

F = ("맑은 고딕", 12); FB = ("맑은 고딕", 12, "bold"); FT = ("맑은 고딕", 16, "bold")
PAPER_LABEL = {"auto": "자동(드라이버 용지)", 58: "58mm", 79: "79mm 롤", 80: "80mm"}
LABEL_PAPER = {v: k for k, v in PAPER_LABEL.items()}
MODE_LABEL = {"escpos": "영수증 프린터(ESC/POS)", "gdi": "일반/라벨 프린터(Windows 드라이버)"}
LABEL_MODE = {v: k for k, v in MODE_LABEL.items()}
LAYOUT_LABEL = {"receipt": "영수증 전체", "label": "라벨(크게 요약)"}
LABEL_LAYOUT = {v: k for k, v in LAYOUT_LABEL.items()}

# ---------------- Firebase 설정 파일 ----------------
def load_fb(base):
    p = os.path.join(base, "firebase_config.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f: return json.load(f)
    return {"enabled": False, "api_key": "", "project_id": "", "email": "", "password": ""}

def save_fb(base, fb, password=None):
    """password: None=변경 없음. keyring 사용 가능하면 자격 증명 관리자에, 아니면 파일에 저장."""
    fb = dict(fb)
    if password:
        try:
            import keyring
            keyring.set_password("festival-receipt", fb["email"], password); fb["password"] = ""
        except Exception:
            fb["password"] = password
    if fb.get("enabled") and not (fb.get("api_key") and fb.get("project_id") and fb.get("email")):
        raise ValueError("Firebase 를 켜려면 API 키, 프로젝트 ID, 이메일이 모두 필요합니다.")
    from storage import atomic_write_json
    atomic_write_json(os.path.join(base, "firebase_config.json"), fb)
    return fb

# ---------------- 프린터 한 대 편집 ----------------
class PrinterRow:
    """프린터 1대 설정 줄: [사용] [프린터 선택▼] [방식▼] [레이아웃▼] [용지▼] [별명] [테스트] [삭제]"""
    def __init__(self, parent, row, p, installed, on_test, on_delete):
        p = appconfig.normalize_printer(p)
        self.v_en = tk.BooleanVar(value=p["enabled"])
        self.v_name = tk.StringVar(value=p["name"])
        self.v_mode = tk.StringVar(value=MODE_LABEL[p["mode"]])
        self.v_layout = tk.StringVar(value=LAYOUT_LABEL[p["layout"]])
        self.v_paper = tk.StringVar(value=PAPER_LABEL.get(p["paper"], PAPER_LABEL["auto"]))
        self.v_label = tk.StringVar(value=p["label"])
        self.extra = {k: v for k, v in p.items() if k in ("font", "max_font_px", "feed_mm")}
        self.ws = [
            tk.Checkbutton(parent, variable=self.v_en),
            ttk.Combobox(parent, textvariable=self.v_name, values=installed, width=26, font=F),
            ttk.Combobox(parent, textvariable=self.v_mode, values=list(MODE_LABEL.values()), state="readonly", width=28, font=F),
            ttk.Combobox(parent, textvariable=self.v_layout, values=list(LAYOUT_LABEL.values()), state="readonly", width=12, font=F),
            ttk.Combobox(parent, textvariable=self.v_paper, values=list(PAPER_LABEL.values()), state="readonly", width=16, font=F),
            tk.Entry(parent, textvariable=self.v_label, width=10, font=F),
            tk.Button(parent, text="테스트 인쇄", font=F, command=lambda: on_test(self.get())),
            tk.Button(parent, text="삭제", font=F, command=lambda: on_delete(self)),
        ]
        for c, wdg in enumerate(self.ws): wdg.grid(row=row, column=c, padx=3, pady=3, sticky="w")
    def get(self):
        p = {"enabled": self.v_en.get(), "name": self.v_name.get().strip(), "mode": LABEL_MODE[self.v_mode.get()],
             "layout": LABEL_LAYOUT[self.v_layout.get()], "paper": LABEL_PAPER[self.v_paper.get()],
             "label": self.v_label.get().strip() or self.v_name.get().strip()}
        p.update(self.extra); return appconfig.normalize_printer(p)
    def destroy(self):
        for wdg in self.ws: wdg.destroy()

class PrinterList(tk.Frame):
    def __init__(self, parent, printers, on_test):
        super().__init__(parent)
        self.pack(fill="x", padx=10, pady=10, anchor="w")
        self.installed = appconfig.list_windows_printers()
        self.on_test, self.rows = on_test, []
        for c, t in enumerate(("사용", "프린터 (Windows에 설치된 목록)", "방식", "레이아웃", "용지 폭", "별명", "", "")):
            tk.Label(self, text=t, font=FB).grid(row=0, column=c, padx=3, sticky="w")
        for p in printers: self.add(p)
        tk.Button(parent, text="＋ 프린터 추가", font=F, command=lambda: self.add({})).pack(anchor="w", padx=10)
        if not self.installed:
            tk.Label(parent, text="※ 설치된 프린터 목록을 읽지 못했습니다. 이름을 직접 입력하세요.", fg="red", font=F).pack(anchor="w", padx=10)
    def add(self, p):
        if not p.get("name") and self.installed and not self.rows: p = dict(p, name=self.installed[0])
        self.rows.append(PrinterRow(self, len(self.rows) + 1, p, self.installed, self.on_test, self.remove))
        self._regrid()
    def remove(self, r):
        r.destroy(); self.rows.remove(r); self._regrid()
    def _regrid(self):
        for i, r in enumerate(self.rows, 1):
            for c, wdg in enumerate(r.ws): wdg.grid(row=i, column=c)
    def get(self): return [r.get() for r in self.rows]

# ---------------- 설정 창 ----------------
def settings_window(root, cfg, base, on_saved, test_print):
    """cfg: 현재 설정(정규화됨). on_saved(new_cfg, fb_changed). test_print(pcfg, cfg)->메시지 또는 예외."""
    win = tk.Toplevel(root); win.title("설정"); win.transient(root); win.grab_set()
    nb = ttk.Notebook(win); nb.pack(fill="both", expand=True, padx=10, pady=10)
    # 1) 가게 정보
    t1 = tk.Frame(nb); nb.add(t1, text="  가게 정보  ")
    v = {k: tk.StringVar(value=str(cfg.get(k, ""))) for k in ("title", "stall_name", "footer", "device_id")}
    for i, (k, lab) in enumerate((("title", "가게/행사 이름 (영수증 제목)"), ("stall_name", "매대 이름 (선택)"),
                                  ("footer", "영수증 하단 문구"), ("device_id", "기기 ID (여러 노트북 구분, 비우면 컴퓨터 이름)"))):
        tk.Label(t1, text=lab, font=F).grid(row=i, column=0, sticky="e", padx=8, pady=6)
        tk.Entry(t1, textvariable=v[k], font=F, width=40).grid(row=i, column=1, sticky="w")
    v_prev = tk.BooleanVar(value=cfg.get("show_preview", True))
    tk.Checkbutton(t1, text="인쇄 전 미리보기 창 보기", variable=v_prev, font=F).grid(row=4, column=1, sticky="w", pady=6)
    v_bak = tk.StringVar(value=cfg.get("backup_dir", "backup"))
    tk.Label(t1, text="백업 폴더 (USB 등)", font=F).grid(row=5, column=0, sticky="e", padx=8)
    bf = tk.Frame(t1); bf.grid(row=5, column=1, sticky="w")
    tk.Entry(bf, textvariable=v_bak, font=F, width=32).pack(side="left")
    def pick():
        d = filedialog.askdirectory(parent=win, title="백업 폴더 선택")
        if d: v_bak.set(os.path.normpath(d))
    tk.Button(bf, text="찾아보기…", font=F, command=pick).pack(side="left", padx=4)
    tk.Label(t1, text=f"데이터 폴더: {base}", font=("맑은 고딕", 10), fg="gray").grid(row=6, column=0, columnspan=2, sticky="w", padx=8, pady=8)
    # 2) 프린터
    t2 = tk.Frame(nb); nb.add(t2, text="  프린터  ")
    def do_test(p):
        tmp = dict(cfg, title=v["title"].get() or cfg.get("title", ""))
        try: messagebox.showinfo("테스트 인쇄", test_print(p, tmp), parent=win)
        except Exception as e: messagebox.showerror("테스트 인쇄 실패", str(e), parent=win)
    plist = PrinterList(t2, cfg.get("printers", []), do_test)
    tk.Label(t2, justify="left", font=("맑은 고딕", 10), fg="gray", text=(
        "· 영수증 프린터(SLK-TS100 등): 방식=영수증 프린터(ESC/POS), 용지 80mm(또는 58mm)\n"
        "· 라벨/일반 프린터: 방식=일반/라벨 프린터, 용지=자동(라벨 크기는 프린터 '인쇄 기본 설정'에서) 또는 79mm 롤")).pack(anchor="w", padx=10)
    # 3) Firebase
    t3 = tk.Frame(nb); nb.add(t3, text="  온라인 동기화(선택)  ")
    fb = load_fb(base)
    fv = {k: tk.StringVar(value=fb.get(k, "")) for k in ("api_key", "project_id", "email")}
    fen = tk.BooleanVar(value=bool(fb.get("enabled")))
    fpw = tk.StringVar()
    tk.Checkbutton(t3, text="Firebase 실시간 전송 사용", variable=fen, font=FB).grid(row=0, column=1, sticky="w", pady=6)
    for i, (k, lab) in enumerate((("api_key", "웹 API 키"), ("project_id", "프로젝트 ID"), ("email", "전용 계정 이메일")), 1):
        tk.Label(t3, text=lab, font=F).grid(row=i, column=0, sticky="e", padx=8, pady=4)
        tk.Entry(t3, textvariable=fv[k], font=F, width=40).grid(row=i, column=1, sticky="w")
    tk.Label(t3, text="비밀번호 (변경할 때만 입력)", font=F).grid(row=4, column=0, sticky="e", padx=8)
    tk.Entry(t3, textvariable=fpw, font=F, width=40, show="*").grid(row=4, column=1, sticky="w")
    tk.Label(t3, text="설정 방법은 사용설명서(README)의 Firebase 항목 참고. 꺼두면 인터넷 없이 모든 기능 동작.",
             font=("맑은 고딕", 10), fg="gray").grid(row=5, column=0, columnspan=2, sticky="w", padx=8, pady=8)
    # 저장
    def save():
        new = dict(cfg, title=v["title"].get().strip(), stall_name=v["stall_name"].get().strip(),
                   footer=v["footer"].get().strip(), device_id=v["device_id"].get().strip(),
                   show_preview=v_prev.get(), backup_dir=v_bak.get().strip() or "backup", printers=plist.get())
        try:
            new = appconfig.save_config(base, new)
            nfb = {"enabled": fen.get(), **{k: x.get().strip() for k, x in fv.items()}, "password": fb.get("password", "")}
            fb_changed = nfb != fb or bool(fpw.get())
            if fb_changed: save_fb(base, nfb, fpw.get() or None)
        except ValueError as e:
            messagebox.showerror("입력 오류", str(e), parent=win); return
        except Exception as e:
            messagebox.showerror("저장 실패", str(e), parent=win); return
        on_saved(new, fb_changed); win.destroy()
    b = tk.Frame(win); b.pack(pady=(0, 10))
    tk.Button(b, text="저장", font=FT, width=8, bg="#4caf50", fg="white", command=save).pack(side="left", padx=5)
    tk.Button(b, text="취소", font=FT, width=8, command=win.destroy).pack(side="left", padx=5)
    win.bind("<Escape>", lambda e: win.destroy())
    return win

# ---------------- 첫 실행 마법사 ----------------
def first_run_wizard(root, base, test_print, set_pin, pin_valid):
    """반환: 'sample' | 'blank' (메뉴 시작 방식) 또는 None(취소). 완료 시 config.json, admin.json, menu.csv 생성."""
    win = tk.Toplevel(root); win.title("처음 설정"); win.grab_set(); win.minsize(820, 460)
    state = {"step": 0, "result": None}
    cfg = appconfig.normalize_config({})
    body = tk.Frame(win); body.pack(fill="both", expand=True, padx=20, pady=15)
    nav = tk.Frame(win); nav.pack(fill="x", padx=20, pady=10)
    v_title, v_stall = tk.StringVar(), tk.StringVar()
    pin1, pin2 = tk.StringVar(), tk.StringVar()
    v_menu = tk.StringVar(value="sample")
    holder = {}

    def clear():
        for wdg in body.winfo_children(): wdg.destroy()
    def page_store():
        tk.Label(body, text="1/4  가게 이름", font=FT).pack(anchor="w")
        tk.Label(body, text="영수증 맨 위에 나올 가게(행사) 이름을 입력하세요.", font=F).pack(anchor="w", pady=5)
        e = tk.Entry(body, textvariable=v_title, font=("맑은 고딕", 16), width=30); e.pack(anchor="w"); e.focus_set()
        tk.Label(body, text="매대 이름 (선택)", font=F).pack(anchor="w", pady=(15, 0))
        tk.Entry(body, textvariable=v_stall, font=F, width=30).pack(anchor="w")
    def page_printer():
        tk.Label(body, text="2/4  프린터 선택", font=FT).pack(anchor="w")
        tk.Label(body, text="목록에서 프린터를 고르고 [테스트 인쇄]로 확인하세요. 나중에 [설정]에서 더 추가할 수 있습니다.", font=F, wraplength=700, justify="left").pack(anchor="w", pady=5)
        def t(p):
            try: messagebox.showinfo("테스트 인쇄", test_print(p, dict(cfg, title=v_title.get())), parent=win)
            except Exception as e: messagebox.showerror("테스트 인쇄 실패", str(e), parent=win)
        holder["pl"] = PrinterList(body, holder.get("printers") or [{}], t)
    def page_pin():
        tk.Label(body, text="3/4  관리자 PIN", font=FT).pack(anchor="w")
        tk.Label(body, text="메뉴 관리·설정을 열 때 쓰는 숫자 4자리 PIN 을 정하세요.", font=F).pack(anchor="w", pady=5)
        for lab, var in (("PIN", pin1), ("PIN 확인", pin2)):
            f = tk.Frame(body); f.pack(anchor="w", pady=4)
            tk.Label(f, text=lab, font=F, width=8, anchor="e").pack(side="left")
            tk.Entry(f, textvariable=var, show="*", font=("맑은 고딕", 16), width=8).pack(side="left")
    def page_menu():
        tk.Label(body, text="4/4  메뉴 시작", font=FT).pack(anchor="w")
        tk.Radiobutton(body, text="예시 메뉴로 시작 (떡볶이, 어묵 등 - 나중에 수정)", variable=v_menu, value="sample", font=F).pack(anchor="w", pady=4)
        tk.Radiobutton(body, text="빈 메뉴로 시작 (완료 후 메뉴 관리 창이 열립니다)", variable=v_menu, value="blank", font=F).pack(anchor="w", pady=4)
    pages = [page_store, page_printer, page_pin, page_menu]

    def leave_check():
        s = state["step"]
        if s == 0 and not v_title.get().strip(): return "가게 이름을 입력하세요."
        if s == 1:
            ps = holder["pl"].get(); holder["printers"] = ps
            if any(not p["name"] for p in ps): return "프린터를 선택하세요. (없으면 행을 삭제)"
        if s == 2:
            if not pin_valid(pin1.get()): return "PIN 은 숫자 4자리여야 합니다."
            if pin1.get() != pin2.get(): return "두 PIN 이 다릅니다."
        return None
    def show():
        clear(); pages[state["step"]]()
        bprev.config(state="normal" if state["step"] else "disabled")
        bnext.config(text="완료" if state["step"] == len(pages) - 1 else "다음 ▶")
    def nxt(e=None):
        err = leave_check()
        if err: messagebox.showwarning("처음 설정", err, parent=win); return
        if state["step"] < len(pages) - 1: state["step"] += 1; show(); return
        c = dict(cfg, title=v_title.get().strip(), stall_name=v_stall.get().strip(), printers=holder.get("printers", []))
        try:
            appconfig.save_config(base, c); set_pin(pin1.get())
            appconfig.create_menu(base, sample=(v_menu.get() == "sample"))
        except Exception as ex:
            messagebox.showerror("저장 실패", str(ex), parent=win); return
        state["result"] = v_menu.get(); win.destroy()
    def prv():
        if state["step"]:
            if state["step"] == 1: holder["printers"] = holder["pl"].get()
            state["step"] -= 1; show()
    bprev = tk.Button(nav, text="◀ 이전", font=F, width=10, command=prv); bprev.pack(side="left")
    tk.Button(nav, text="취소", font=F, width=8, command=win.destroy).pack(side="right", padx=5)
    bnext = tk.Button(nav, text="다음 ▶", font=FB, width=10, bg="#4caf50", fg="white", command=nxt); bnext.pack(side="right")
    win.bind("<Return>", nxt)
    show(); win.focus_force(); root.wait_window(win)
    return state["result"]
