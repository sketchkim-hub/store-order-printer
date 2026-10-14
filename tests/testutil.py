import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["FESTIVAL_RECEIPT_DATA"] = tempfile.mkdtemp()  # 실제 사용자 데이터 건드리지 않음
MENU = """key,name,price
1,닭꼬치,4000
2,닭발,4000
3,돼지껍데기,4000
4,두부김치,3000
5,회오리감자,3000
6,오징어구이,3000
7,치킨,5000
8,군밤,3000
9,타코야끼,3000
10,가래떡구이,2000
11,특화상품 시제품,3000
12,"꽈배기,도너츠",2000
13,수육,3000
14,고구마,3000
"""
CONFIG = {"title": "떡축제 먹거리", "stall_name": "먹거리 매대", "footer": "이용해 주셔서 감사합니다!",
          "show_preview": True, "backup_dir": "backup", "device_id": "",
          "printers": [{"name": "SLK-TS100", "label": "영수증", "mode": "escpos", "layout": "receipt", "enabled": True},
                       {"name": "LABEL", "label": "라벨", "mode": "gdi", "layout": "label", "enabled": False}]}
def fixture(d, menu=True, config=True):
    if menu: open(os.path.join(d, "menu.csv"), "w", encoding="utf-8").write(MENU)
    if config: json.dump(CONFIG, open(os.path.join(d, "config.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return d
