# -*- coding: utf-8 -*-
"""여러 프린터 지원: escpos(RAW, 영수증 프린터) / gdi(Windows 드라이버, 라벨 프린터 등 모든 프린터)"""
import datetime

def get_printers(cfg):
    """config 의 printers 목록. 없으면 예전 printer_name 으로 1대 구성 (하위 호환)."""
    lst = cfg.get("printers")
    if not lst:
        lst = [{"name": cfg.get("printer_name", ""), "mode": cfg.get("print_mode", "escpos"),
                "layout": cfg.get("layout", "receipt"), "enabled": True}]
    out = []
    for p in lst:
        q = {"mode": "escpos", "layout": "receipt", "enabled": True, "font": "Malgun Gothic"}
        q.update(p); q.setdefault("label", q["name"]); out.append(q)
    return out

def build_label(cfg, item, qty, no, now=None):
    """라벨용 간단 레이아웃. item: 메뉴 dict(+qty) 또는 주문 list [{name,price,qty,...}]. 반환: [(텍스트, 크기배율)]"""
    now = now or datetime.datetime.now()
    order = item if isinstance(item, list) else [dict(item, qty=qty, amount=item["price"] * qty)]
    total = sum(l["price"] * l["qty"] for l in order)
    if len(order) == 1:
        l = order[0]
        return [(cfg["title"], 1.0), (l["name"], 2.0), (f"수량 {l['qty']}   {total:,}원", 1.4),
                (f"No.{no:04d}  {now:%m-%d %H:%M}", 1.0)]
    big = 1.5 if len(order) <= 3 else 1.2
    return ([(cfg["title"], 1.0), (f"No.{no:04d}  {now:%m-%d %H:%M}", 1.0)]
            + [(f"{l['name']} x{l['qty']}", big) for l in order]
            + [(f"합계 {total:,}원", 1.6)])

def text_to_lines(text):
    return [(l, 1.0) for l in text.rstrip("\n").split("\n")]

# ---------- GDI 배치 계산 (순수 함수, 테스트 가능) ----------
def gdi_layout(lines, page_w, page_h, measure, max_base=None, min_base=8, gap=1.2, roll=False):
    """lines=[(text, scale)], measure(text, height)->width(px).
    가장 넓은 줄이 page_w 에 맞도록 기준 글자 높이를 정함. roll=True 면 한 장(높이=내용 길이).
    반환: (base_height, pages=[[(text, height, y)]], total_height)"""
    max_base = max_base or max(min_base, page_h // 4 if not roll else page_w // 8)
    base = max_base
    while base > min_base:
        fits_w = all(measure(t, int(base * s)) <= page_w for t, s in lines if t.strip())
        fits_h = roll or len(lines) > 8 or sum(int(int(base * s) * gap) for _, s in lines) <= page_h  # 라벨은 한 장에
        if fits_w and fits_h: break
        base -= 1
    pages, cur, y = [], [], 0
    for t, s in lines:
        h = int(base * s); step = int(h * gap)
        if not roll and cur and y + step > page_h:
            pages.append(cur); cur, y = [], 0
        cur.append((t, h, y)); y += step
    if cur: pages.append(cur)
    if not roll and len(pages) == 1 and len(lines) <= 8:  # 라벨: 한 장에 맞으면 세로 가운데
        off = max(0, (page_h - y) // 2); pages = [[(t, h, yy + off) for t, h, yy in pages[0]]]
    return base, pages, y

def mm_to_px(mm, dpi): return int(mm * dpi / 25.4)

# ---------- ctypes 기반 GDI (win32ui/MFC 불필요) ----------
HORZRES, VERTRES, LOGPIXELSX, LOGPIXELSY = 8, 10, 88, 90
DM_PAPERSIZE, DM_PAPERLENGTH, DM_PAPERWIDTH = 0x2, 0x4, 0x8
DM_OUT_BUFFER, DM_IN_BUFFER = 2, 8
OFF_FIELDS, OFF_PAPERSIZE, OFF_PAPERLENGTH, OFF_PAPERWIDTH = 72, 78, 80, 82  # DEVMODEW 오프셋

def patch_devmode(buf, width_mm, length_mm):
    """DEVMODEW 바이트 버퍼에 사용자 지정 용지(0.1mm 단위) 설정."""
    import struct
    f = struct.unpack_from("<I", buf, OFF_FIELDS)[0] | DM_PAPERSIZE | DM_PAPERLENGTH | DM_PAPERWIDTH
    struct.pack_into("<I", buf, OFF_FIELDS, f)
    struct.pack_into("<h", buf, OFF_PAPERSIZE, 256)  # DMPAPER_USER
    struct.pack_into("<h", buf, OFF_PAPERLENGTH, min(32767, max(300, int(length_mm * 10))))
    struct.pack_into("<h", buf, OFF_PAPERWIDTH, int(width_mm * 10))
    return buf

class CtypesGDI:
    """gdi32/winspool 직접 호출. 하나의 DC 를 감쌈."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.c, self.wt = ctypes, wintypes
        self.gdi, self.ws, self.k32 = ctypes.WinDLL("gdi32", use_last_error=True), ctypes.WinDLL("winspool.drv", use_last_error=True), ctypes.WinDLL("kernel32")
        g = self.gdi; H = wintypes.HANDLE
        g.CreateDCW.restype = H; g.CreateDCW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p]
        g.CreateFontW.restype = H
        g.CreateFontW.argtypes = [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [wintypes.LPCWSTR]
        g.SelectObject.restype = H; g.SelectObject.argtypes = [H, H]
        g.DeleteObject.argtypes = [H]; g.DeleteDC.argtypes = [H]
        g.GetDeviceCaps.argtypes = [H, ctypes.c_int]
        g.TextOutW.argtypes = [H, ctypes.c_int, ctypes.c_int, wintypes.LPCWSTR, ctypes.c_int]
        g.GetTextExtentPoint32W.argtypes = [H, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.SIZE)]
        g.SetBkMode.argtypes = [H, ctypes.c_int]
        for n in ("StartPage", "EndPage", "EndDoc", "AbortDoc"): getattr(g, n).argtypes = [H]
        class DOCINFOW(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_int), ("lpszDocName", wintypes.LPCWSTR), ("lpszOutput", wintypes.LPCWSTR),
                        ("lpszDatatype", wintypes.LPCWSTR), ("fwType", wintypes.DWORD)]
        self.DOCINFOW = DOCINFOW
        g.StartDocW.argtypes = [H, ctypes.POINTER(DOCINFOW)]
        self.ws.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(H), ctypes.c_void_p]
        self.ws.ClosePrinter.argtypes = [H]
        self.ws.DocumentPropertiesW.argtypes = [wintypes.HWND, H, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
        self.ws.DocumentPropertiesW.restype = ctypes.c_long
        self.hdc = None; self.fonts = {}

    def _err(self, what):
        e = self.c.get_last_error()
        return OSError(e, f"{what} 실패 (Windows 오류 {e})", None, e) if e else OSError(f"{what} 실패")

    def get_devmode(self, name):
        """DEVMODEW 바이트 버퍼 (없으면 None)."""
        h = self.wt.HANDLE()
        if not self.ws.OpenPrinterW(name, self.c.byref(h), None): raise self._err("OpenPrinter")
        try:
            n = self.ws.DocumentPropertiesW(None, h, name, None, None, 0)
            if n <= 0: return None
            buf = self.c.create_string_buffer(n)
            if self.ws.DocumentPropertiesW(None, h, name, buf, None, DM_OUT_BUFFER) < 0: return None
            return buf
        finally: self.ws.ClosePrinter(h)

    def validate_devmode(self, name, buf):
        h = self.wt.HANDLE()
        if not self.ws.OpenPrinterW(name, self.c.byref(h), None): return buf
        try: self.ws.DocumentPropertiesW(None, h, name, buf, buf, DM_IN_BUFFER | DM_OUT_BUFFER)
        finally: self.ws.ClosePrinter(h)
        return buf

    def open(self, name, devmode=None):
        self.close()
        self.hdc = self.gdi.CreateDCW("WINSPOOL", name, None, devmode)
        if not self.hdc: raise self._err(f"CreateDC('{name}')")
        self.gdi.SetBkMode(self.hdc, 1)  # TRANSPARENT

    def caps(self, idx): return self.gdi.GetDeviceCaps(self.hdc, idx)

    def font(self, face, h, bold):
        k = (face, h, bold)
        if k not in self.fonts:
            f = self.gdi.CreateFontW(-max(1, h), 0, 0, 0, 700 if bold else 400, 0, 0, 0, 129, 0, 0, 5, 0, face)  # HANGUL_CHARSET, CLEARTYPE
            if not f: raise self._err("CreateFont")
            self.fonts[k] = f
        return self.fonts[k]

    def measure(self, face, text, h, bold=False):
        old = self.gdi.SelectObject(self.hdc, self.font(face, h, bold))
        sz = self.wt.SIZE(); self.gdi.GetTextExtentPoint32W(self.hdc, text, len(text), self.c.byref(sz))
        self.gdi.SelectObject(self.hdc, old); return sz.cx

    def start_doc(self, title):
        di = self.DOCINFOW(self.c.sizeof(self.DOCINFOW), title, None, None, 0)
        if self.gdi.StartDocW(self.hdc, self.c.byref(di)) <= 0: raise self._err("StartDoc")
    def start_page(self):
        if self.gdi.StartPage(self.hdc) <= 0: raise self._err("StartPage")
    def text(self, face, x, y, t, h, bold):
        old = self.gdi.SelectObject(self.hdc, self.font(face, h, bold))
        self.gdi.TextOutW(self.hdc, x, y, t, len(t)); self.gdi.SelectObject(self.hdc, old)
    def end_page(self):
        if self.gdi.EndPage(self.hdc) <= 0: raise self._err("EndPage")
    def end_doc(self):
        if self.gdi.EndDoc(self.hdc) <= 0: raise self._err("EndDoc")
    def abort_doc(self): self.gdi.AbortDoc(self.hdc)
    def close(self):
        for f in self.fonts.values(): self.gdi.DeleteObject(f)
        self.fonts = {}
        if self.hdc: self.gdi.DeleteDC(self.hdc); self.hdc = None

def default_backend():
    try:
        return CtypesGDI()
    except (OSError, AttributeError, ImportError) as e:
        raise OSError(f"GDI 인쇄를 사용할 수 없습니다 (Windows 전용, gdi32 로드 실패: {e}). "
                      "이 프린터는 mode 를 'escpos' 로 쓰거나 Windows 에서 실행하세요.")

def print_gdi(pcfg, lines, title="Receipt", backend=None):
    """Windows 드라이버로 텍스트 그리기 (ctypes, win32ui 불필요).
    paper_width_mm 지정 시 연속 롤지: 폭 고정, 길이 = 내용 길이 (DEVMODE 사용자 용지, 실패 시 기본 용지)."""
    g = backend or default_backend()
    name, face = pcfg["name"], pcfg.get("font", "Malgun Gothic")
    roll_mm = pcfg.get("paper_width_mm")
    try:
        g.open(name, None)
        dpi_y = g.caps(LOGPIXELSY) or 203; dpi_x = g.caps(LOGPIXELSX) or 203
        meas = lambda t, h: g.measure(face, t, h)
        if roll_mm:
            pw = mm_to_px(pcfg.get("printable_mm", roll_mm - 7), dpi_x)  # 79mm → 약 72mm
            pw = min(pw, g.caps(HORZRES) or pw)
            base, pages, total = gdi_layout(lines, pw, 10 ** 9, meas, roll=True,
                                            max_base=pcfg.get("max_font_px") or mm_to_px(4, dpi_y))
            length_mm = int(total * 25.4 / dpi_y) + pcfg.get("feed_mm", 15)
            dm = None
            try:
                dm = g.get_devmode(name)
                if dm is not None: dm = g.validate_devmode(name, patch_devmode(dm, roll_mm, length_mm))
            except Exception:
                dm = None  # 사용자 지정 용지 실패 → 기본 용지
            if dm is not None: g.open(name, dm)
            ph = g.caps(VERTRES)
            if ph and ph < total:  # 드라이버가 길이를 무시 → 페이지 높이로 분할
                pages = gdi_layout(lines, pw, ph, meas, max_base=base, min_base=base)[1]
            x0 = max(0, ((g.caps(HORZRES) or pw) - pw) // 2)
        else:
            pw, ph = g.caps(HORZRES), g.caps(VERTRES)
            if pw <= 0 or ph <= 0: raise OSError(f"프린터 '{name}' 의 용지 크기를 읽을 수 없습니다.")
            base, pages, _ = gdi_layout(lines, pw, ph, meas, max_base=pcfg.get("max_font_px"))
            x0 = 0
        g.start_doc(title)
        try:
            for page in pages:
                g.start_page()
                for t, h, y in page:
                    if t: g.text(face, x0, y, t, h, h > base)
                g.end_page()
            g.end_doc()
        except Exception:
            g.abort_doc(); raise
    finally:
        g.close()
