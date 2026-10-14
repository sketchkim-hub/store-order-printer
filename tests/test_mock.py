import testutil
import receipt, tempfile
receipt.BASE = testutil.fixture(tempfile.mkdtemp())
cfg = receipt.load_config(); menu = receipt.load_menu()
sent = []
for it in (menu[0], menu[11]):
    no, text, msg = receipt.sell(cfg, it, 2, printer=lambda n, d: sent.append(d))
    print(text); print(msg)
assert sent[0].startswith(b"\x1b@") and sent[0].endswith(b"\x1dVB\x00") and "닭꼬치".encode("cp949") in sent[0]
print(receipt.output(cfg, "x", printer=lambda n, d: 1/0))
print(receipt.daily_summary(cfg)); print("OK", len(menu))
