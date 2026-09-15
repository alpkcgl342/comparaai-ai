"""Ürünleri AI prompt'larına yazarken tek noktadan formatlamak için.

/recommend, /compare, /followup üçü de aynı "- Ad (Marka), Özellikler: ..."
satırını tekrar tekrar yazıyordu; artık burada tek yerde ve artık ürünün
(varsa) ProductAiScore verisini de (özellikle future_proof_score —
"3 yıl sonra hâlâ kullanılabilir mi?" tarzı sorular için) satıra ekliyor.
"""
from typing import Any


def format_product_line(product: Any) -> str:
    """product: main.py'deki Product pydantic modeli (id, name, brand, specs, ai_score?)."""
    line = f"- {product.name} ({product.brand}), Özellikler: {product.specs}"

    score = getattr(product, "ai_score", None)
    if score:
        bits = []
        if score.get("overall_score") is not None:
            bits.append(f"genel AI puanı: {score['overall_score']}/100")
        if score.get("future_proof_score") is not None:
            bits.append(f"geleceğe dönüklük puanı: {score['future_proof_score']}/100")
        if score.get("value_score") is not None:
            bits.append(f"fiyat/performans puanı: {score['value_score']}/100")
        if score.get("ai_summary"):
            bits.append(f"AI özeti: {score['ai_summary']}")
        if bits:
            line += " | " + "; ".join(bits)

    return line


def format_products_block(products: list[Any]) -> str:
    return "\n".join(format_product_line(p) for p in products)


_LEVEL_NOTES = {
    "basit": "Kullanıcının teknik seviyesi: BAŞLANGIÇ/ÇOCUK. Teknik terim kullanma, günlük "
    "hayattan somut benzetmelerle çok basit anlat.",
    "teknik": "Kullanıcının teknik seviyesi: TEKNİK. Teknik terimleri rahatça kullanabilirsin, "
    "gerekirse kısa açıklama ekle.",
    "uzman": "Kullanıcının teknik seviyesi: UZMAN. Teknik terimleri açıklamadan kullan, "
    "isteniyorsa mimari/donanım detaylarına değinebilirsin.",
}


def expertise_level_note(level: str | None) -> str:
    """Faz 4 — kullanıcının seçtiği teknik seviyeye göre prompt'a eklenecek not.

    'normal' veya boş/None için not eklenmez (zaten promptların varsayılan tonu budur).
    """
    if not level:
        return ""
    note = _LEVEL_NOTES.get(level)
    return f"{note}\n\n" if note else ""
