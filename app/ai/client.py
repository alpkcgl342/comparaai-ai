"""Merkezi Gemini AI istemci katmanı.

Roadmap Faz 0: "tüm AI çağrılarının tek bir merkezi katmandan geçtiğinden emin ol".
Yeni bir AI özelliği eklerken doğrudan google.genai kullanma — bu modüldeki
generate() / generate_stream() fonksiyonlarını kullan. Böylece retry/timeout,
loglama ve (ileride) cache/model seçimi tek noktadan yönetilir.
"""
import logging
import os
import time
from typing import Iterator, Optional

from google import genai
from google.genai import errors, types

from . import usage_log

logger = logging.getLogger("comparaai.ai.client")

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
DEFAULT_TIMEOUT_MS = int(os.getenv("GEMINI_TIMEOUT_MS", "30000"))
MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
RETRY_BASE_DELAY_SECONDS = 1.0

_client: Optional["genai.Client"] = None


def get_client() -> "genai.Client":
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY tanımlı değil. .env dosyasını (bkz. .env.example) kontrol edin."
            )
        _client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=DEFAULT_TIMEOUT_MS),
        )
    return _client


def _is_retryable(exc: Exception) -> bool:
    """5xx sunucu hatalarında ve 429 rate limit'te retry edilir; diğer 4xx hatalarında edilmez."""
    if isinstance(exc, errors.ServerError):
        return True
    if isinstance(exc, errors.ClientError) and getattr(exc, "code", None) == 429:
        return True
    return False


def generate(
    prompt: str,
    system_instruction: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    feature: str = "unknown",
    max_retries: int = MAX_RETRIES,
) -> str:
    """Tek seferlik (streaming olmayan) bir AI çağrısı yapar ve metni döndürür.

    - Sunucu hatalarında (5xx) ve rate limit'te (429) exponential backoff ile retry eder.
    - Diğer hatalarda (400, 401, vb.) hemen fırlatır — anlamsız retry yapmaz.
    - Her denemenin süresini ve (varsa) token kullanımını usage_log'a yazar.
    """
    client = get_client()
    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        started_at = time.monotonic()
        try:
            interaction = client.interactions.create(
                model=model,
                input=prompt,
                system_instruction=system_instruction,
            )
            usage_log.log_call(
                feature=feature,
                model=model,
                attempt=attempt,
                duration_seconds=time.monotonic() - started_at,
                usage=getattr(interaction, "usage", None),
                success=True,
            )
            return interaction.output_text
        except Exception as exc:  # noqa: BLE001 - retry katmanı kasıtlı olarak geniş yakalıyor
            last_error = exc
            usage_log.log_call(
                feature=feature,
                model=model,
                attempt=attempt,
                duration_seconds=time.monotonic() - started_at,
                usage=None,
                success=False,
                error=str(exc),
            )

            if attempt >= max_retries or not _is_retryable(exc):
                raise

            delay = RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "Gemini çağrısı başarısız (deneme %s/%s, feature=%s), %.1fs sonra tekrar denenecek: %s",
                attempt, max_retries, feature, delay, exc,
            )
            time.sleep(delay)

    raise last_error  # pragma: no cover - yukarıdaki döngü her zaman return/raise ile biter


def generate_stream(
    prompt: str,
    system_instruction: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    feature: str = "unknown",
) -> Iterator[str]:
    """Streaming AI çağrısı yapar; metin parçalarını (chunk) tek tek üretir (yield).

    NOT (Faz 0 - altyapı): Bu fonksiyon henüz hiçbir endpoint'te kullanılmıyor.
    Bir sohbet endpoint'ini streaming'e geçirirken, kullanılan google-genai
    sürümünde stream event'inin gerçek alan adını (output_text / delta / text)
    doğrulayın — aşağıdaki çıkarım en yaygın adları dener ama SDK sürümüne göre
    değişebilir.

    Retry burada kasıtlı olarak UYGULANMAZ: bir streaming yanıtın ortasında hata
    olursa kullanıcıya zaten kısmi metin gitmiş olabilir, sessizce yeniden
    denemek tutarsız/yarım cevaplara yol açar.
    """
    client = get_client()
    started_at = time.monotonic()
    try:
        stream = client.interactions.create(
            model=model,
            input=prompt,
            system_instruction=system_instruction,
            stream=True,
        )
        for event in stream:
            chunk = (
                getattr(event, "output_text", None)
                or getattr(event, "delta", None)
                or getattr(event, "text", None)
            )
            if chunk:
                yield chunk
        usage_log.log_call(
            feature=feature,
            model=model,
            attempt=1,
            duration_seconds=time.monotonic() - started_at,
            usage=None,
            success=True,
            streamed=True,
        )
    except Exception as exc:
        usage_log.log_call(
            feature=feature,
            model=model,
            attempt=1,
            duration_seconds=time.monotonic() - started_at,
            usage=None,
            success=False,
            error=str(exc),
            streamed=True,
        )
        raise
