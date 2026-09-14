"""Redis tabanlı basit response cache.

main.py içindeki her endpoint aynı mantığı tekrar etmesin diye buraya taşındı.
Faz 1'de Supabase'e geçildiğinde (ai_cache tablosu) burada sadece get_cached/
set_cached implementasyonu değişecek, çağıran kod aynı kalabilir.
"""
import hashlib
import json
import os

import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
CACHE_TTL_SECONDS = int(os.getenv("AI_CACHE_TTL_SECONDS", str(60 * 60 * 24)))  # 24 saat

_redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def make_cache_key(prefix: str, data: dict) -> str:
    """Verilen veriyi tutarlı bir şekilde hashleyip cache anahtarı üretir."""
    serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
    hash_value = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"{prefix}:{hash_value}"


def get_cached(key: str):
    try:
        value = _redis_client.get(key)
        return json.loads(value) if value else None
    except Exception:
        return None  # Redis erişilemezse cache'siz devam et, hata verme


def set_cached(key: str, value: dict):
    try:
        _redis_client.setex(key, CACHE_TTL_SECONDS, json.dumps(value, ensure_ascii=False))
    except Exception:
        pass  # Redis erişilemezse sessizce geç, uygulama çalışmaya devam etsin
