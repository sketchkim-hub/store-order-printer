# -*- coding: utf-8 -*-
"""정전에 안전한 파일 쓰기: 원자적 교체 + fsync, 추가 전용 저널"""
import json, os

def _fsync_dir(d):
    if os.name == "nt": return  # Windows는 디렉터리 fsync 미지원
    fd = os.open(d, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

def atomic_write(path, text):
    d = os.path.dirname(os.path.abspath(path)); os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path); _fsync_dir(d)

def atomic_write_json(path, obj):
    atomic_write(path, json.dumps(obj, ensure_ascii=False, indent=1))

def journal_append(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())

def journal_read(path):
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try: out.append(json.loads(line))
                except ValueError: pass  # 정전으로 잘린 마지막 줄 무시
    return out
