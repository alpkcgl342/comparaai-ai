"""Basit fuzzy string eşleştirme yardımcıları (Faz 2 — Haber↔Ürün bağlantısı).

Harici bir kütüphane veya embedding API'si gerektirmez — stdlib `difflib`
kullanır. Roadmap'in "fuzzy match + AI doğrulama" isteğindeki ilk adım budur;
ikinci adım (AI doğrulama) main.py'de ayrıca Gemini'ye soruluyor.
"""
from difflib import SequenceMatcher
from typing import TypedDict


class ProductCandidate(TypedDict):
    id: str
    name: str
    brand: str


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def find_candidates(
    entity_name: str,
    products: list[ProductCandidate],
    min_score: float = 0.45,
    max_candidates: int = 3,
) -> list[tuple[ProductCandidate, float]]:
    """entity_name'e en çok benzeyen ürünleri (skor, azalan) döndürür.

    Hem "Marka Ürün" hem sadece "Ürün" adına karşı skorlanır, ikisinden
    yüksek olan alınır (kullanıcı/haber genelde markayı ayrı yazar).
    """
    scored: list[tuple[ProductCandidate, float]] = []

    for product in products:
        full_label = f"{product['brand']} {product['name']}"
        score = max(
            _similarity(entity_name, full_label),
            _similarity(entity_name, product["name"]),
        )
        if score >= min_score:
            scored.append((product, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:max_candidates]
