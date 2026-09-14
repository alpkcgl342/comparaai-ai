"""'/compare-sources' endpoint'i için prompt (Faz 2 — Çoklu Kaynak Haber Analizi).

Duplicate tespitiyle aynı olay etrafında gruplanmış birden fazla haberi
(farklı yazar/kaynak alanına sahip olabilir) karşılaştırıp ortak noktaları,
farklı vurguları ve olası taraflılık sinyallerini özetler.
"""


def build_compare_sources_prompt(articles: list[dict]) -> str:
    """articles: [{"author": ..., "title": ..., "content": ...}, ...] (2+ eleman)"""
    articles_text = "\n\n".join(
        f'KAYNAK {i + 1} ({a.get("author") or "Yazar belirtilmemiş"}):\n'
        f'Başlık: {a["title"]}\n'
        f'İçerik: {a["content"]}'
        for i, a in enumerate(articles)
    )
    return f"""Aşağıda AYNI OLAYI anlatan {len(articles)} farklı haber var:

{articles_text}

GÖREVİN:
Bu haberleri karşılaştırarak:
1. "consensus": Tüm kaynakların ORTAK OLARAK belirttiği, üzerinde hemfikir olunan noktalar
   (2-4 madde).
2. "differences": Kaynaklar arasında farklılık gösteren noktalar — biri bir detayı verirken
   diğeri vermemesi, farklı rakamlar/ifadeler kullanılması, farklı bir yöne vurgu yapılması
   (varsa; her farkı hangi kaynağın belirttiğiyle birlikte açıkla).
3. "emphasis_notes": Her kaynağın haberi hangi açıdan/vurguyla ele aldığına dair kısa bir not
   (örn. "Kaynak 1 teknik özelliklere odaklanmış, Kaynak 2 fiyat/rekabet açısına vurgu yapmış").
   Bu TARAFLILIK SUÇLAMASI değil, sadece vurgu farkı gözlemi olmalı — nötr bir dille yaz.

KURALLAR:
- SADECE verilen metinlere dayan, uydurma bilgi ekleme.
- Kaynakları "doğru/yanlış" olarak yargılama — sadece farkları objektif şekilde raporla.
- Gerçek bir fark yoksa "differences" için boş dizi döndürebilirsin.

ÇOK ÖNEMLİ: Cevabını SADECE geçerli bir JSON nesnesi olarak ver, başka hiçbir açıklama ekleme.
Tam olarak şu formatta:
{{"consensus": ["<string>", ...], "differences": ["<string>", ...], "emphasis_notes": ["<string>", ...]}}"""
