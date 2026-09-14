"""'/detect-duplicates' endpoint'i için prompt (Faz 2 — Duplicate Haber Tespiti).

Embedding/pgvector yerine Gemini'nin kendisine semantik benzerlik
sorduruyoruz — fuzzy string eşleşmesinden farklı olarak, farklı kaynaktan
farklı yazılmış ama AYNI OLAYI anlatan haberleri de yakalayabiliyor.
"""


def build_duplicate_check_prompt(
    new_title: str, new_summary: str, candidates: list[dict]
) -> str:
    """candidates: [{"id": ..., "title": ..., "summary": ...}, ...]"""
    candidates_text = "\n".join(
        f'- id="{c["id"]}": "{c["title"]}" — {c["summary"]}' for c in candidates
    )
    return f"""YENİ HABER:
Başlık: {new_title}
Özet: {new_summary}

MEVCUT HABERLER (son günlerden):
{candidates_text}

GÖREVİN:
Yukarıdaki mevcut haberlerden hangileri, yeni haberle AYNI OLAYI/GELİŞMEYİ anlatıyor?
Farklı kaynaktan alınmış, farklı yazılmış ama özünde aynı haberi (örn. aynı ürün lansmanı,
aynı şirket açıklaması, aynı olay) anlatan haberleri "duplicate" say.

KURALLAR:
- Sadece GERÇEKTEN aynı olayı anlatanları listele. Aynı şirket/ürün hakkında olsa bile
  FARKLI bir gelişmeyi anlatıyorsa (örn. biri lansman haberi, diğeri fiyat haberi) duplicate
  SAYMA.
- similarity_score 0.0-1.0 arası: 1.0 = kesinlikle aynı haber, 0.7-0.9 = büyük olasılıkla
  aynı olay, altını dahil etme.
- Hiçbiri eşleşmiyorsa boş dizi döndür.
- Sadece gerçekten emin olduğun eşleşmeleri (skor >= 0.7) dahil et.

ÇOK ÖNEMLİ: Cevabını SADECE geçerli bir JSON dizisi olarak ver, başka hiçbir açıklama ekleme.
Tam olarak şu formatta:
[{{"article_id": "<string>", "similarity_score": <0.0-1.0>, "reason": "<kısa gerekçe>"}}, ...]"""
