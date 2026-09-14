"""Token/maliyet ve çağrı loglama katmanı.

Faz 0 kapsamında: her AI çağrısının hangi özellik (feature) tarafından,
hangi modelle, ne kadar sürede ve başarılı/başarısız olarak yapıldığını
yerel bir JSONL dosyasına (logs/ai_usage.jsonl) yazar.

Faz 1'de Supabase'e geçildiğinde `ai_usage_logs` tablosu oluşacak; o noktada
bu modüldeki log_call() fonksiyonunun gövdesi Supabase'e insert atacak şekilde
değiştirilecek, main.py ve diğer çağıran kodlar HİÇ değişmeyecek.
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("comparaai.ai.usage")

LOG_DIR = Path(os.getenv("AI_USAGE_LOG_DIR", "logs"))
LOG_FILE = LOG_DIR / "ai_usage.jsonl"


def _extract_token_counts(usage: Any) -> dict:
    """Gemini interaction.usage nesnesinden token sayılarını güvenli şekilde çıkarır.

    SDK sürümüne göre alan adları değişebilir; bulunamayan alanlar None bırakılır.
    """
    if usage is None:
        return {"input_tokens": None, "output_tokens": None, "total_tokens": None}

    def _get(*names):
        for name in names:
            value = getattr(usage, name, None)
            if value is not None:
                return value
        return None

    return {
        "input_tokens": _get("input_tokens", "prompt_tokens", "input_token_count"),
        "output_tokens": _get("output_tokens", "completion_tokens", "output_token_count"),
        "total_tokens": _get("total_tokens", "total_token_count"),
    }


def log_call(
    feature: str,
    model: str,
    attempt: int,
    duration_seconds: float,
    usage: Any = None,
    success: bool = True,
    error: Optional[str] = None,
    streamed: bool = False,
) -> None:
    entry = {
        "timestamp": time.time(),
        "feature": feature,
        "model": model,
        "attempt": attempt,
        "duration_seconds": round(duration_seconds, 3),
        "success": success,
        "streamed": streamed,
        "error": error,
        **_extract_token_counts(usage),
    }

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Loglama asla ana isteği kesmemeli.
        logger.exception("AI kullanım logu yazılamadı: %s", entry)
