import testutil, os, json, tempfile, shutil
import appconfig, receipt
# 데이터 폴더 결정
ad = tempfile.mkdtemp()
assert appconfig.data_dir({"FESTIVAL_RECEIPT_DATA": os.path.join(ad, "x")}, ad) == os.path.join(ad, "x")
assert appconfig.data_dir({"APPDATA": os.path.join(ad, "roam")}, ad) == os.path.join(ad, "roam", "FestivalReceipt")
os.makedirs(os.path.join(ad, "data")); assert appconfig.data_dir({"APPDATA": "zz"}, ad) == os.path.join(ad, "data")  # 포터블
assert os.path.isdir(os.path.join(ad, "roam", "FestivalReceipt"))
# 기본값 병합 / 예전 설정 호환
c = appconfig.normalize_config({})
assert c["show_preview"] is True and c["printers"] == [] and c["backup_dir"] == "backup"
old = appconfig.normalize_config({"title": "T", "printer_name": "SLK"})
assert old["printers"][0]["name"] == "SLK" and old["printers"][0]["mode"] == "escpos" and old["printers"][0]["paper"] == 80
roll = appconfig.normalize_printer({"name": "L", "mode": "gdi", "paper_width_mm": 79})
assert roll["paper"] == 79 and roll["paper_width_mm"] == 79 and roll["printable_mm"] == 72
lab = appconfig.normalize_printer({"name": "L", "mode": "gdi", "paper": "auto"}); assert "paper_width_mm" not in lab
assert appconfig.normalize_printer({"name": "L", "mode": "gdi"})["paper"] == "auto"
esc58 = appconfig.normalize_printer({"name": "S", "paper": "58"}); assert esc58["paper"] == 58 and "paper_width_mm" not in esc58
assert appconfig.normalize_printer({"name": "S", "paper": 123})["paper"] == "auto"
assert appconfig.cols_for(esc58) == 32 and appconfig.cols_for(roll) == 42
# 검증
e = appconfig.validate_config(appconfig.normalize_config({"title": " ", "device_id": "노트북 1",
                                                          "printers": [{"name": ""}, {"name": "X", "mode": "bad"}]}))
assert len(e) == 4, e
# 저장 (원자적) / 첫 실행
d = tempfile.mkdtemp(); assert appconfig.is_first_run(d)
try: appconfig.save_config(d, {"title": ""}); assert False
except ValueError: assert appconfig.is_first_run(d)  # 잘못된 설정은 저장 안 됨
saved = appconfig.save_config(d, {"title": "가게", "printers": [{"name": "SLK", "paper": 58}]})
assert not appconfig.is_first_run(d) and not os.path.exists(os.path.join(d, "config.json.tmp"))
j = json.load(open(os.path.join(d, "config.json"), encoding="utf-8")); assert j["printers"][0]["paper"] == 58
# 메뉴 생성 (샘플/빈)
appconfig.create_menu(d, sample=True); receipt.BASE = d
m = receipt.load_menu(); assert m and m[0]["name"] == "떡볶이"
appconfig.create_menu(d, sample=False); assert receipt.load_menu() == []
os.remove(os.path.join(d, "menu.csv")); assert receipt.load_menu() == [] and os.path.exists(os.path.join(d, "menu.csv"))
# 58mm 영수증: 32칸
cfg = receipt.load_config()
sent = []
msg = receipt.test_print_one({"name": "SLK", "paper": 58}, cfg, printer=lambda n, b: sent.append(b))
assert "SLK" in msg and sent
t, _ = receipt.render_for(cfg, cfg["printers"][0], {"key": 1, "name": "떡볶이", "price": 4000}, 2, 1)
assert max(receipt.w(x) for x in t.split("\n")) == 32 and receipt.WIDTH == 42, t
try: receipt.test_print_one({"name": ""}, cfg); assert False
except receipt.PrintError: pass
# Firebase 설정 저장
import settings_ui
try: settings_ui.save_fb(d, {"enabled": True, "api_key": "", "project_id": "", "email": ""}); assert False
except ValueError: pass
settings_ui.save_fb(d, {"enabled": False, "api_key": "", "project_id": "", "email": "", "password": ""})
assert settings_ui.load_fb(d)["enabled"] is False
# 예전 버전 데이터 이전
old = testutil.fixture(tempfile.mkdtemp()); os.makedirs(os.path.join(old, "sales")); open(os.path.join(old, "sales", "x.csv"), "w").write("a")
new = tempfile.mkdtemp()
got = appconfig.migrate_legacy(new, old)
assert set(got) == {"config.json", "menu.csv", "sales"} and os.path.exists(os.path.join(new, "sales", "x.csv"))
assert os.path.exists(os.path.join(old, "config.json")) and appconfig.migrate_legacy(new, old) == []
shutil.rmtree(d); shutil.rmtree(ad); print("SETTINGS TESTS OK")
