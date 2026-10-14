# -*- coding: utf-8 -*-
"""설정/데이터 경로 관리. 사용자가 JSON 을 직접 고칠 필요 없도록 기본값 병합·검증·원자적 저장."""
import copy, csv, os, shutil, sys
from storage import atomic_write_json, atomic_write

APP_NAME = "FestivalReceipt"

def app_dir():
    """exe(또는 스크립트)가 있는 폴더."""
    return os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))

def resource_dir():
    """exe 에 묶인 리소스(menu.sample.csv, app.ico) 위치."""
    return getattr(sys, "_MEIPASS", app_dir())

def data_dir(env=None, appdir=None):
    """데이터 폴더 결정:
    1) 환경변수 FESTIVAL_RECEIPT_DATA
    2) 포터블: exe 옆에 'data' 폴더 또는 'portable.txt' 가 있으면 <exe폴더>\\data
    3) Windows: %APPDATA%\\FestivalReceipt   그 외: ~/.FestivalReceipt"""
    env = os.environ if env is None else env
    appdir = appdir or app_dir()
    if env.get("FESTIVAL_RECEIPT_DATA"): d = env["FESTIVAL_RECEIPT_DATA"]
    elif os.path.isdir(os.path.join(appdir, "data")) or os.path.exists(os.path.join(appdir, "portable.txt")):
        d = os.path.join(appdir, "data")
    elif env.get("APPDATA"): d = os.path.join(env["APPDATA"], APP_NAME)
    else: d = os.path.join(os.path.expanduser("~"), "." + APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d

PAPER_CHOICES = ["auto", 58, 79, 80]       # auto = 드라이버 기본(라벨 등)
MODES, LAYOUTS = ["escpos", "gdi"], ["receipt", "label"]

DEFAULT_PRINTER = {"name": "", "label": "영수증", "mode": "escpos", "layout": "receipt",
                   "paper": 80, "enabled": True, "font": "Malgun Gothic"}

DEFAULT_CONFIG = {
    "title": "우리 가게", "stall_name": "", "footer": "이용해 주셔서 감사합니다!",
    "printers": [], "show_preview": True, "cut_paper": True, "preview_only": False,
    "backup_dir": "backup", "device_id": "",
}

def cols_for(pcfg):
    """ESC/POS 한 줄 글자 수(반각): 58mm=32, 79/80mm=42"""
    p = (pcfg or {}).get("paper", 80)
    return 32 if p == 58 else 42

def normalize_printer(p):
    q = copy.deepcopy(DEFAULT_PRINTER); q.update(p or {})
    if q.get("mode") == "gdi" and "paper" not in (p or {}) and "paper_width_mm" not in (p or {}):
        q["paper"] = "auto"  # 라벨/일반 프린터 기본: 드라이버 용지
    if "paper_width_mm" in q and q.get("paper") in (None, 80) and "paper" not in (p or {}):
        q["paper"] = q["paper_width_mm"]  # 예전 설정 호환
    if q["paper"] not in PAPER_CHOICES:
        try: q["paper"] = int(q["paper"])
        except (TypeError, ValueError): q["paper"] = "auto"
        if q["paper"] not in PAPER_CHOICES: q["paper"] = "auto"
    # gdi + 롤 폭 지정 → 연속 롤지 모드 (printers.print_gdi 가 paper_width_mm 사용)
    q.pop("paper_width_mm", None)
    if q["mode"] == "gdi" and isinstance(q["paper"], int):
        q["paper_width_mm"] = q["paper"]; q.setdefault("printable_mm", {58: 48, 79: 72, 80: 72}[q["paper"]])
    q.setdefault("label", q["name"]); q["label"] = q["label"] or q["name"] or "프린터"
    return q

def normalize_config(cfg):
    c = copy.deepcopy(DEFAULT_CONFIG); c.update(cfg or {})
    if not c.get("printers") and c.get("printer_name"):  # 예전 printer_name 호환
        c["printers"] = [{"name": c["printer_name"], "mode": c.get("print_mode", "escpos"),
                          "layout": c.get("layout", "receipt")}]
    c["printers"] = [normalize_printer(p) for p in c["printers"]]
    return c

def validate_config(c):
    errs = []
    if not str(c.get("title", "")).strip(): errs.append("가게/행사 이름을 입력하세요.")
    for i, p in enumerate(c.get("printers", []), 1):
        if not str(p.get("name", "")).strip(): errs.append(f"프린터 {i}: 프린터를 선택하세요.")
        if p.get("mode") not in MODES: errs.append(f"프린터 {i}: 방식이 올바르지 않습니다.")
        if p.get("layout") not in LAYOUTS: errs.append(f"프린터 {i}: 레이아웃이 올바르지 않습니다.")
        if p.get("paper") not in PAPER_CHOICES: errs.append(f"프린터 {i}: 용지 폭이 올바르지 않습니다.")
    did = str(c.get("device_id", ""))
    if did and not all(ch.isalnum() or ch in "-_" for ch in did): errs.append("기기 ID 는 영문/숫자/-/_ 만 가능합니다.")
    if len(did) > 30: errs.append("기기 ID 는 30자 이하로 입력하세요.")
    return errs

def config_path(base): return os.path.join(base, "config.json")

def is_first_run(base): return not os.path.exists(config_path(base))

def save_config(base, c):
    c = normalize_config(c)
    errs = validate_config(c)
    if errs: raise ValueError("\n".join(errs))
    out = {k: v for k, v in c.items() if k not in ("printer_name", "print_mode", "layout")}
    atomic_write_json(config_path(base), out)
    return c

def list_windows_printers():
    """설치된 Windows 프린터 이름 목록 (Windows 가 아니면 빈 목록)."""
    try:
        import win32print
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        return sorted({p[2] for p in win32print.EnumPrinters(flags, None, 1)})
    except Exception:
        return []

def create_menu(base, sample=True):
    """첫 실행: menu.csv 생성 (샘플 복사 또는 빈 메뉴)."""
    dst = os.path.join(base, "menu.csv")
    src = os.path.join(resource_dir(), "menu.sample.csv")
    if sample and os.path.exists(src): shutil.copyfile(src, dst)
    else: atomic_write(dst, "key,name,price\n")
    return dst

MIGRATE_ITEMS = ["config.json", "menu.csv", "admin.json", "counter.json", "firebase_config.json",
                 "sales", "backup", "queue", "preview"]

def migrate_legacy(base, src=None):
    """예전 버전(데이터를 프로그램 폴더에 저장)에서 업그레이드: 새 데이터 폴더가 비어 있으면 복사.
    원본은 지우지 않음. 반환: 복사한 항목 목록"""
    import shutil
    src = src or app_dir()
    if os.path.abspath(src) == os.path.abspath(base) or not is_first_run(base): return []
    if not os.path.exists(os.path.join(src, "config.json")): return []
    done = []
    for n in MIGRATE_ITEMS:
        a, b = os.path.join(src, n), os.path.join(base, n)
        if not os.path.exists(a) or os.path.exists(b): continue
        (shutil.copytree if os.path.isdir(a) else shutil.copy2)(a, b); done.append(n)
    return done
