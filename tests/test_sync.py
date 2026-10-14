import testutil
import os, sys, shutil, tempfile, datetime, json
import firebase_sync as fs, receipt
from firebase_sync import HttpError
tmp = tempfile.mkdtemp()
class Mock:  # 가짜 Firestore 서버
    def __init__(s): s.docs, s.online, s.calls = {}, True, 0
    def __call__(s, m, url, body=None, tok=None):
        s.calls += 1
        if not s.online: raise OSError("network down")
        if "signInWithPassword" in url: return {"idToken": "T", "localId": "UID1", "expiresIn": "3600"}
        did = url.split("documentId=")[1]
        if did in s.docs: raise HttpError(409)
        s.docs[did] = body; return {}
srv = Mock()
cli = fs.FirestoreClient({"api_key": "k", "project_id": "p", "email": "e", "password": "x"}, http=srv)
w = fs.SyncWorker(tmp, cli)
sale = {"sale_id": "20261014-0001-PC1", "item": "닭꼬치", "price": 4000, "qty": 1, "total": 4000}
# 1) 오프라인 → 대기열 유지
srv.online = False; w.enqueue(sale); w.enqueue(dict(sale, sale_id="20261014-0002-PC1")); w.flush_once()
assert w.status() == ("offline", 2), w.status()
# 2) 복구 → 전송, 대기열 비움
srv.online = True; w.flush_once(); assert w.status() == ("synced", 0) and len(srv.docs) == 2
# 3) 재시도(이미 전송된 건 재큐잉) → 409 → 중복 없음
w.enqueue(sale); w.flush_once(); assert w.status() == ("synced", 0) and len(srv.docs) == 2
assert srv.docs["20261014-0001-PC1"]["fields"]["price"] == {"integerValue": "4000"}
assert srv.docs["20261014-0001-PC1"]["fields"]["uid"] == {"stringValue": "UID1"}
# 4) 서버 500 → 대기 유지
def bad(*a, **k): raise HttpError(503)
cli.http = bad; w.enqueue(dict(sale, sale_id="20261014-0003-PC1")); w.flush_once()
assert w.status() == ("offline", 1); cli.http = srv; w.flush_once(); assert len(srv.docs) == 3
# 5) 미설정 → disabled
assert fs.SyncWorker(tmp, None).status()[0] == "disabled"
# 6) 판매 → 백업/저널/큐
receipt.BASE = tmp
testutil.fixture(tmp)
cfg = receipt.load_config(); cfg["device_id"] = "PC1"; cfg["preview_only"] = True
receipt.SYNC = fs.SyncWorker(tmp, None)
no, _, msg = receipt.sell(cfg, receipt.load_menu()[0], 2)
d = datetime.date.today().isoformat()
j = receipt.journal_read if hasattr(receipt, "journal_read") else __import__("storage").journal_read
bj = j(os.path.join(tmp, "backup", f"journal_{d}.jsonl"))
assert bj[0]["total"] == 8000 and bj[0]["items"][0]["qty"] == 2 and os.path.exists(os.path.join(tmp, "backup", d, bj[0]["sale_id"] + ".json"))
assert len(receipt.SYNC.pending()) == 1, msg
print("ALL TESTS OK", bj[0]["sale_id"], msg)
shutil.rmtree(tmp)
