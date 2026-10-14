import testutil
import os, shutil, tempfile, datetime
import receipt, firebase_sync as fs
tmp = tempfile.mkdtemp(); receipt.BASE = tmp
testutil.fixture(tmp)
cfg = receipt.load_config(); cfg["device_id"] = "PC1"
menu = receipt.load_menu(); receipt.SYNC = fs.SyncWorker(tmp, None)
d = datetime.date.today().isoformat()
jr = lambda: __import__("storage").journal_read(os.path.join(tmp, "sales", f"journal_{d}.jsonl"))
# 정렬: 모든 줄 폭 <= 42, 품목 줄 우측 정렬
t, _ = receipt.build_receipt(cfg, menu[11], 12, 1)
L = t.split("\n"); assert all(receipt.w(x) <= 42 for x in L)
hdr = [x for x in L if x.startswith("품목")][0]; row = [x for x in L if x.startswith("꽈배기")][0]
assert receipt.w(hdr) == receipt.w(row) == 42, (hdr, row)
assert receipt.w(hdr[:hdr.index("수량") + 2]) == receipt.w(row[:row.rindex("12") + 2])  # 수량 열 끝 일치
print(t)
# 취소: 미리보기만 → 번호 소모 없음
assert receipt.peek_no() == 1 and receipt.peek_no() == 1 and jr() == []
# 인쇄 성공 → 기록
sent = []
ok, msg = receipt.confirm_sale(cfg, menu[0], 3, printer=lambda n, b: sent.append(b)); print(msg)
assert ok and len(sent) == 1 and jr()[0]["items"][0]["qty"] == 3 and jr()[0]["total"] == 12000 and jr()[0]["receipt_no"] == 1 and receipt.peek_no() == 2
assert b"0001" in sent[0]
# 인쇄 실패 + 저장 거부 → 기록 안 함, 번호 유지
def bad(n, b): raise OSError(1801, "OpenPrinter", "invalid printer name")
asked = []
ok, msg = receipt.confirm_sale(cfg, menu[1], 1, printer=bad, on_fail=lambda m: asked.append(m) or False); print(msg)
assert not ok and len(jr()) == 1 and receipt.peek_no() == 2 and "프린터 이름" in asked[0]
# 실패 + 저장 수락 → 미리보기 파일 + 기록
ok, msg = receipt.confirm_sale(cfg, menu[1], 1, printer=bad, on_fail=lambda m: True); print(msg)
assert ok and len(jr()) == 2 and os.listdir(os.path.join(tmp, "preview"))
# 일반 예외 메시지
try: receipt.try_print(cfg, "x", printer=lambda n, b: 1 / 0); assert False
except receipt.PrintError as e: assert "프린터 오류" in str(e)
assert len(receipt.SYNC.pending()) == 2
shutil.rmtree(tmp); print("PREVIEW TESTS OK")
