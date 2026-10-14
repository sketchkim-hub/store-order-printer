import os, sys, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import sampledata, sales_reader as sr
TODAY = datetime.date(2026, 10, 14)
d = sampledata.make(TODAY.isoformat()); before = sampledata.snapshot(d)
t = sr.today_sales(d, TODAY)
assert t["total"] == 26000 and t["order_count"] == 3 and t["item_count"] == 8 and t["skipped_rows"] == 1, t
assert t["items"][0] == {"name": "떡볶이", "qty": 3, "amount": 12000} and {"name": "어묵", "qty": 4, "amount": 12000} in t["items"]
r = sr.item_sales(d, "2026-10-01", "2026-10-14")
assert r["total"] == 26000 + 8000 + 13000 and r["order_count"] == 3 + 1 + 2, r
assert [x["date"] for x in r["daily"]] == ["2026-10-01", "2026-10-02", "2026-10-14"]
assert r["daily"][1] == {"date": "2026-10-02", "total": 13000, "order_count": 2, "item_count": 4}
assert {"name": "김밥", "qty": 3, "amount": 9000} in r["items"]
assert sr.item_sales(d, "2026-09-01", "2026-09-02")["total"] == 0
for a, b in (("2026-10-15", "2026-10-01"), ("2026/10/01", "2026-10-02"), ("2026-13-01", "2026-10-02"), ("2025-01-01", "2026-10-14"), ("", "2026-10-01")):
    try: sr.item_sales(d, a, b); assert False, (a, b)
    except sr.DataError: pass
m = sr.menu(d)["items"]; assert m[2] == {"key": 3, "name": "꽈배기,도너츠", "price": 2000}
assert sr.menu(os.path.join(d, "nope"))["items"] == []
assert sr.resolve_data_dir({"FESTIVAL_RECEIPT_DATA_DIR": d}) == os.path.abspath(d)
assert sr.resolve_data_dir({"FESTIVAL_RECEIPT_DATA": d}) == os.path.abspath(d)
assert sr.resolve_data_dir({"APPDATA": "/x"}) == os.path.join("/x", "FestivalReceipt")
nd = os.path.join(d, "not_created"); sr.today_sales(nd); assert not os.path.exists(nd)  # 폴더 생성 안 함
assert sampledata.snapshot(d) == before, "data dir changed!"
print("READER TESTS OK")
