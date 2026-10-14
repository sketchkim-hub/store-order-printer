import testutil
import os, csv, shutil, tempfile, datetime, json
import receipt, printers as prn, firebase_sync as fs, storage
tmp = tempfile.mkdtemp(); receipt.BASE = tmp
testutil.fixture(tmp)
cfg = receipt.load_config(); cfg["device_id"] = "PC1"; menu = receipt.load_menu()
receipt.SYNC = fs.SyncWorker(tmp, None)
# --- Cart ---
c = receipt.Cart()
c.add(menu[0]); c.add(menu[2]); c.add(menu[0]); c.add(menu[2], 2)
assert [(l["name"], l["qty"]) for l in c.lines] == [("닭꼬치", 2), ("돼지껍데기", 3)] and c.total() == 2 * 4000 + 3 * 4000
assert c.change(1, -1) == 1 and c.lines[1]["qty"] == 2
assert c.change(0, -2) is None and len(c) == 1  # 0 → 삭제
c.remove(0); assert len(c) == 0 and c.total() == 0
c.add(menu[0], 5000); assert c.lines[0]["qty"] == 999
c.clear()
for m in menu: c.add(m)
assert len(c) == 14
# --- 주문 영수증 ---
c.clear(); c.add(menu[0]); c.add(menu[0]); c.add(menu[2], 3); c.add(menu[10])
order = c.order()
t, total = receipt.build_receipt(cfg, order, None, 7)
print(t)
assert total == 8000 + 12000 + 3000 and "합계 (6개)" in t and all(receipt.w(x) <= 42 for x in t.split("\n"))
lbl = prn.build_label(cfg, order, None, 7); assert any("합계 23,000원" in x for x, _ in lbl) and len(lbl) == 6
assert prn.build_label(cfg, menu[0], 2, 1)[1] == ("닭꼬치", 2.0)  # 1품목 라벨 그대로
# --- 확정: 영수증 1장, 번호 1개, 주문 전체 기록 ---
sent = []
ok, msg = receipt.confirm_sale(cfg, order, None, printer=lambda n, d: sent.append(d), targets=[prn.get_printers(cfg)[0]])
print(msg); assert ok and len(sent) == 1 and receipt.peek_no() == 2
d = datetime.date.today().isoformat()
j = storage.journal_read(os.path.join(tmp, "sales", f"journal_{d}.jsonl"))[0]
assert j["total"] == 23000 and len(j["items"]) == 3 and j["items"][1] == {"key": 3, "name": "돼지껍데기", "price": 4000, "qty": 3, "amount": 12000}
b = json.load(open(os.path.join(tmp, "backup", d, j["sale_id"] + ".json"), encoding="utf-8")); assert b == j
q = json.load(open(os.path.join(tmp, "queue", j["sale_id"] + ".json"), encoding="utf-8")); assert q["items"] == j["items"]
rows = list(csv.DictReader(open(os.path.join(tmp, "sales", d + ".csv"), encoding="utf-8-sig")))
assert len(rows) == 3 and {r["번호"] for r in rows} == {"1"}
# --- 취소된 미리보기는 기록 없음 (번호 유지) ---
assert receipt.peek_no() == 2
# --- 예전 1품목 기록 + 새 기록 합산 요약 ---
with open(os.path.join(tmp, "sales", d + ".csv"), "a", newline="", encoding="utf-8-sig") as f:
    csv.writer(f).writerow([99, "09:00:00", "닭꼬치", 4000, 1, 4000])  # 예전 형식 행
s = receipt.daily_summary(cfg); print(s)
assert "닭꼬치 x3" in s and "27,000원" in s and "영수증 2건 / 7개" in s
# --- Firestore 필드 (배열/맵) ---
f = fs.to_fields(dict(j, uid="U"))["fields"]
v = f["items"]["arrayValue"]["values"][1]["mapValue"]["fields"]
assert v["qty"] == {"integerValue": "3"} and v["name"] == {"stringValue": "돼지껍데기"} and f["total"] == {"integerValue": "23000"}
# --- 빈 주문 거부 ---
try: receipt.record_sale(cfg, [], None); assert False
except ValueError: pass
shutil.rmtree(tmp); print("CART TESTS OK")
