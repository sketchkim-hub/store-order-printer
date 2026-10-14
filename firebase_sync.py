# -*- coding: utf-8 -*-
"""Firestore REST 동기화 (선택 기능). 관리자 키 없이 이메일/비밀번호 로그인 사용.
대기열: queue/<sale_id>.json (판매 1건 = 파일 1개, 원자적 기록). 성공 시 삭제.
중복 방지: 문서 ID = sale_id, createDocument 사용 → 이미 있으면 409 = 성공 처리."""
import json, os, threading, time, urllib.request, urllib.error, urllib.parse
from storage import atomic_write_json

class HttpError(Exception):
    def __init__(self, code, body=""): super().__init__(f"HTTP {code}"); self.code = code

def http_json(method, url, body=None, token=None, timeout=10):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    if token: req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, e.read().decode("utf-8", "replace"))

def load_firebase_config(base):
    p = os.path.join(base, "firebase_config.json")
    if not os.path.exists(p): return None
    with open(p, encoding="utf-8") as f: c = json.load(f)
    if not c.get("enabled", True) or not c.get("api_key") or not c.get("project_id"): return None
    if not c.get("password"):
        try:
            import keyring
            c["password"] = keyring.get_password("festival-receipt", c["email"])
        except Exception: pass
    return c if c.get("password") else None

def to_value(v):
    if isinstance(v, bool): return {"booleanValue": v}
    if isinstance(v, int): return {"integerValue": str(v)}
    if isinstance(v, list): return {"arrayValue": {"values": [to_value(x) for x in v]}}
    if isinstance(v, dict): return {"mapValue": {"fields": {k: to_value(x) for k, x in v.items()}}}
    return {"stringValue": str(v)}

def to_fields(sale):
    return {"fields": {k: to_value(v) for k, v in sale.items()}}

class FirestoreClient:
    def __init__(self, cfg, http=http_json):
        self.c, self.http, self.token, self.exp = cfg, http, None, 0
    def _auth(self):
        if self.token and time.time() < self.exp - 60: return self.token
        r = self.http("POST", "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key="
                      + urllib.parse.quote(self.c["api_key"]),
                      {"email": self.c["email"], "password": self.c["password"], "returnSecureToken": True})
        self.token, self.uid, self.exp = r["idToken"], r["localId"], time.time() + int(r.get("expiresIn", 3600))
        return self.token
    def create_sale(self, sale):
        tok = self._auth()
        base = f"https://firestore.googleapis.com/v1/projects/{self.c['project_id']}/databases/(default)/documents/sales"
        body = to_fields(dict(sale, uid=self.uid))
        try:
            self.http("POST", base + "?documentId=" + urllib.parse.quote(sale["sale_id"]), body, tok)
        except HttpError as e:
            if e.code == 409: return  # 이미 존재 = 이전 시도 성공 → 중복 없음
            if e.code == 401: self.token = None
            raise

class SyncWorker:
    """백그라운드 업로드. status(): ('disabled'|'synced'|'waiting'|'offline', 대기건수)"""
    def __init__(self, base, client=None, interval=15):
        self.qdir = os.path.join(base, "queue"); os.makedirs(self.qdir, exist_ok=True)
        self.client, self.interval = client, interval
        self.offline, self.ev, self.lock = False, threading.Event(), threading.Lock()
    def enqueue(self, sale):
        atomic_write_json(os.path.join(self.qdir, sale["sale_id"] + ".json"), sale)
        self.ev.set()
    def pending(self):
        return sorted(f for f in os.listdir(self.qdir) if f.endswith(".json"))
    def flush_once(self):
        if not self.client: return
        with self.lock:
            for fn in self.pending():
                p = os.path.join(self.qdir, fn)
                try:
                    with open(p, encoding="utf-8") as f: sale = json.load(f)
                except ValueError:
                    os.replace(p, p + ".bad"); continue
                try:
                    self.client.create_sale(sale); os.remove(p); self.offline = False
                except HttpError as e:
                    self.offline = e.code >= 500 or e.code in (401, 429); self.last_error = str(e); break
                except Exception as e:  # 네트워크 끊김
                    self.offline = True; self.last_error = str(e); break
    def status(self):
        if not self.client: return ("disabled", len(self.pending()))
        n = len(self.pending())
        return ("synced", 0) if n == 0 else (("offline" if self.offline else "waiting"), n)
    def start(self):
        if getattr(self, "_started", False): return
        self._started = True
        def loop():
            while True:
                self.flush_once(); self.ev.wait(self.interval); self.ev.clear()
        threading.Thread(target=loop, daemon=True).start()
