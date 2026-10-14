import testutil
import os, shutil, tempfile, glob, receipt
tmp = tempfile.mkdtemp(); receipt.BASE = tmp; testutil.fixture(tmp, config=False)
m, e = receipt.validate_menu([("닭꼬치", "4,000"), (" 수육 ", "3000원")]); assert not e and m[1] == {"key": 2, "name": "수육", "price": 3000}
_, e = receipt.validate_menu([("", "1000"), ("A", "0"), ("B", "-5"), ("C", "abc")]); assert len(e) == 4, e
assert receipt.validate_menu([])[1]
new, _ = receipt.validate_menu([("꽈배기,도너츠", 2000), ("닭발", 4000)])
receipt.save_menu(new)
assert receipt.load_menu() == new and glob.glob(os.path.join(tmp, "menu.csv.bak_*"))
assert [receipt.key_hint(k) for k in (1, 10, 12, 14, 15)] == ["1", "0", "F12", "Shift+F2", ""]
shutil.rmtree(tmp); print("MENU TESTS OK")
tmp = tempfile.mkdtemp(); receipt.BASE = tmp
assert not receipt.pin_is_set()
for bad in ("123", "12345", "abcd", "12a4"):
    try: receipt.set_pin(bad); assert False
    except ValueError: pass
receipt.set_pin("0427"); txt = open(os.path.join(tmp, "admin.json")).read()
assert "0427" not in txt and "salt" in txt and receipt.pin_is_set()
assert receipt.verify_pin("0427", now=1000)[0]
for i in range(4): assert not receipt.verify_pin("1111", now=1000)[0]
ok, m = receipt.verify_pin("1111", now=1000); assert not ok and "잠" in m
assert not receipt.verify_pin("0427", now=1030)[0]       # 잠금 중엔 맞아도 거부
assert receipt.verify_pin("0427", now=1061)[0]           # 60초 후 해제
receipt.set_pin("9999"); assert receipt.verify_pin("9999", now=2000)[0] and not receipt.verify_pin("0427", now=2000)[0]
shutil.rmtree(tmp); print("PIN TESTS OK")
