import testutil
import os, shutil, tempfile, datetime
import receipt, printers as prn, firebase_sync as fs
# 하위 호환
old = prn.get_printers({"printer_name": "P1"}); assert old[0]["name"] == "P1" and old[0]["mode"] == "escpos"
assert prn.get_printers({"printer_name": "P", "print_mode": "gdi"})[0]["mode"] == "gdi"
meas = lambda t, h: receipt.w(t) * h // 2  # 가짜 글자폭: 반각=높이/2
L = [("떡축제", 1.0), ("가래떡구이", 2.0), ("수량 1  2,000원", 1.4), ("No.0001", 1.0)]
base, pages, _ = prn.gdi_layout(L, 400, 240, meas)  # 소형 라벨 50x30mm@203dpi 정도
assert len(pages) == 1 and all(meas(t, h) <= 400 for t, h, y in pages[0]) and all(y + h <= 240 for t, h, y in pages[0]), (base, pages)
t, _ = receipt.build_receipt({"title": "T", "stall_name": "S", "footer": "F"}, {"name": "닭꼬치", "price": 4000}, 1, 1)
lines = prn.text_to_lines(t)
base, pages, _ = prn.gdi_layout(lines, 400, 240, meas, max_base=30)
assert len(pages) > 1 and sum(len(p) for p in pages) == len(lines)  # 여러 장 분할
assert all(y + int(h * 1.2) <= 240 + h for p in pages for t2, h, y in p)
pw = prn.mm_to_px(72, 203); base, pages, total = prn.gdi_layout(lines, pw, 10**9, meas, roll=True, max_base=prn.mm_to_px(4, 203))
assert len(pages) == 1 and all(meas(x, h) <= pw for x, h, y in pages[0] if x.strip()) and total > 0  # 79mm 롤: 한 장
print("79mm roll: width px", pw, "font", base, "length mm", int(total * 25.4 / 203))
# 다중 프린터 판매
tmp = tempfile.mkdtemp(); receipt.BASE = tmp
testutil.fixture(tmp)
cfg = receipt.load_config(); cfg["device_id"] = "PC1"; receipt.SYNC = fs.SyncWorker(tmp, None)
menu = receipt.load_menu()
ps = prn.get_printers(cfg); A, B = ps[0], dict(ps[1], name="LBL")
got = {}
ok, msg = receipt.confirm_sale(cfg, menu[0], 2, printer=lambda n, d: got.setdefault(n, d), targets=[A, B]); print(msg)
assert ok and isinstance(got["SLK-TS100"], bytes) and got["LBL"][1][0] == "닭꼬치" and receipt.peek_no() == 2
# 한 대 실패 → 기록 + 경고
def half(n, d):
    if n == "LBL": raise OSError(1801, "x", "y")
warned = []
def of(m): return False
of.warn = warned.append
ok, msg = receipt.confirm_sale(cfg, menu[1], 1, printer=half, on_fail=of, targets=[A, B]); print(msg)
assert ok and "일부 실패" in msg and "[라벨]" in warned[0] and receipt.peek_no() == 3
# 모두 실패 + 거부 → 기록 없음, 프린터별 사유
rep = []
ok, msg = receipt.confirm_sale(cfg, menu[1], 1, printer=lambda n, d: 1 / 0, on_fail=lambda m: rep.append(m) or False, targets=[A, B])
assert not ok and "[영수증]" in rep[0] and "[라벨]" in rep[0] and receipt.peek_no() == 3
# 테스트 인쇄: 프린터별 오류
try: receipt.try_print(cfg, "a\nb", printer=half, targets=[A, B]); assert False
except receipt.PrintError as e: assert "[라벨]" in str(e) and "[영수증]" not in str(e)
shutil.rmtree(tmp); print("PRINTER TESTS OK")
# ---- ctypes GDI 백엔드 모의 테스트 ----
class FakeGDI:
    def __init__(s, w=576, h=400, dm=True, fail=None):
        s.w, s.h, s.dm, s.fail, s.log, s.dev = w, h, dm, fail, [], None
    def open(s, n, dm): s.log.append(("open", n, dm is not None)); s.dev = dm
    def caps(s, i):
        if i == prn.VERTRES and s.dev is not None: return 10 ** 6
        return {prn.HORZRES: s.w, prn.VERTRES: s.h, prn.LOGPIXELSX: 203, prn.LOGPIXELSY: 203}[i]
    def measure(s, f, t, h, b=False): return receipt.w(t) * h // 2
    def get_devmode(s, n): return bytearray(220) if s.dm else None
    def validate_devmode(s, n, b): s.patched = bytes(b); return b
    def start_doc(s, t): s.log.append("doc")
    def start_page(s): s.log.append("page")
    def text(s, f, x, y, t, h, b):
        if s.fail == "text": raise OSError("boom")
        s.log.append(("t", t, x, y, h))
    def end_page(s): s.log.append("endpage")
    def end_doc(s): s.log.append("enddoc")
    def abort_doc(s): s.log.append("abort")
    def close(s): s.log.append("close")
import struct
g = FakeGDI(w=400, h=240); prn.print_gdi({"name": "LBL"}, prn.build_label({"title": "떡축제"}, {"name": "수육", "price": 3000}, 2, 7), backend=g)
assert g.log.count("page") == 1 and g.log[-2:] == ["enddoc", "close"] and any(x[1] == "수육" for x in g.log if x[0] == "t")
g = FakeGDI(w=400, h=240); prn.print_gdi({"name": "A4"}, lines, backend=g); assert g.log.count("page") > 1  # 분할
g = FakeGDI(w=640); prn.print_gdi({"name": "R", "paper_width_mm": 79}, lines, backend=g)
assert g.log.count("page") == 1 and ("open", "R", True) in g.log
assert struct.unpack_from("<hhh", g.patched, 78)[0] == 256 and struct.unpack_from("<h", g.patched, 82)[0] == 790
g = FakeGDI(w=640, h=300, dm=False); prn.print_gdi({"name": "R", "paper_width_mm": 79}, lines, backend=g)
assert g.log.count("page") > 1  # DEVMODE 없음 → 기본 용지로 분할
g = FakeGDI(fail="text")
try: prn.print_gdi({"name": "X"}, lines, backend=g); assert False
except OSError: assert "abort" in g.log and g.log[-1] == "close"
# Linux: 백엔드 없음 → 명확한 오류 → PrintError
try: receipt.send_to({}, {"name": "X", "mode": "gdi", "label": "라벨"}, "t", [("t", 1.0)]); assert False
except receipt.PrintError as e: print("non-windows msg:", str(e)[:60])
print("GDI CTYPES TESTS OK")
