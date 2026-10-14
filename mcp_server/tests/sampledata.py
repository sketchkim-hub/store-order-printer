# 테스트용 데이터 폴더 생성 (임시 폴더에만 씀)
import csv, json, os, tempfile
H = ["번호", "시각", "품목", "단가", "수량", "금액"]
def make(today):
    d = tempfile.mkdtemp(prefix="frmcp_")
    s = os.path.join(d, "sales"); os.makedirs(s)
    def day_csv(day, rows):
        with open(os.path.join(s, day + ".csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(H); w.writerows(rows)
    # 오늘: 예전 1품목 행 + 새 여러 품목 주문 (번호 2 = 3품목)
    day_csv(today, [[1, "10:00:00", "떡볶이", 4000, 1, 4000],
                    [2, "10:05:00", "떡볶이", 4000, 2, 8000], [2, "10:05:00", "어묵", 3000, 3, 9000], [2, "10:05:00", "음료", 2000, 1, 2000],
                    [3, "11:00:00", "어묵", 3000, 1, 3000], ["x", "", "깨진줄", "abc", 1, 1]])
    day_csv("2026-10-01", [[1, "12:00:00", "순대", 4000, 2, 8000]])
    # CSV 없이 저널만 있는 날 (새 형식 + 예전 형식)
    with open(os.path.join(s, "journal_2026-10-02.jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"receipt_no": 1, "time": "09:00:00", "items": [{"key": 1, "name": "떡볶이", "price": 4000, "qty": 1, "amount": 4000},
                                                                            {"key": 2, "name": "김밥", "price": 3000, "qty": 2, "amount": 6000}], "total": 10000}, ensure_ascii=False) + "\n")
        f.write(json.dumps({"receipt_no": 2, "item": "김밥", "price": 3000, "qty": 1, "total": 3000}, ensure_ascii=False) + "\n")
        f.write('{"receipt_no": 3, "items": [{"na')  # 정전으로 잘린 줄
    with open(os.path.join(d, "menu.csv"), "w", encoding="utf-8") as f:
        f.write('key,name,price\n1,떡볶이,4000\n2,어묵,3000\n3,"꽈배기,도너츠",2000\n')
    # 건드리면 안 되는 파일
    os.makedirs(os.path.join(d, "queue"))
    with open(os.path.join(d, "counter.json"), "w") as f: f.write('{"date": "%s", "no": 3}' % today)
    return d

def snapshot(d):
    out = {}
    for root, dirs, files in os.walk(d):
        out[root] = sorted(dirs)
        for fn in files:
            p = os.path.join(root, fn); st = os.stat(p)
            out[p] = (st.st_size, st.st_mtime_ns, open(p, "rb").read())
    return out
