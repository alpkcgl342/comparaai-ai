"""'/explain-term' endpoint'i için prompt (Faz 4 — Teknoloji Terimleri AI).

4 seviye: basit (çocuk/başlangıç), normal, teknik, uzman.
"""

LEVEL_INSTRUCTIONS = {
    "basit": (
        "ÇOCUK/BAŞLANGIÇ SEVİYESİ: Hiç teknik bilgisi olmayan, hatta bir çocuğa anlatır gibi "
        "açıkla. Günlük hayattan somut bir benzetme kullan (örn. 'RAM, masanın üzeri gibidir — "
        "ne kadar genişse o kadar çok şeyi aynı anda açık tutabilirsin'). Teknik terim, kısaltma "
        "veya sayı KULLANMA. 2-3 kısa cümle yeterli."
    ),
    "normal": (
        "NORMAL SEVİYE: Ortalama bir teknoloji kullanıcısına (teknik geçmişi olmayan ama günlük "
        "teknoloji kullanan biri) anlatır gibi açıkla. Gerekirse 1 teknik terim kullanabilirsin "
        "ama hemen günlük dille açıkla. 3-4 cümle."
    ),
    "teknik": (
        "TEKNİK SEVİYE: Teknolojiyle ilgilenen, temel kavramlara aşina birine anlatır gibi açıkla. "
        "İlgili teknik terimleri rahatça kullanabilirsin, kısa açıklamalarını ekle. Nasıl "
        "çalıştığına dair biraz detay ver. 4-6 cümle."
    ),
    "uzman": (
        "UZMAN SEVİYE: Alanında bilgili birine anlatır gibi açıkla. Teknik terimleri açıklamadan "
        "kullanabilirsin. Mümkünse mimari/teknik detaylara, varsa yaygın standartlara/versiyonlara "
        "değin. Gerekliyse rakip yaklaşımlarla kısa bir karşılaştırma yapabilirsin."
    ),
}


def build_explain_term_prompt(term: str, level: str) -> str:
    level_instruction = LEVEL_INSTRUCTIONS.get(level, LEVEL_INSTRUCTIONS["normal"])
    return f"""Açıklanacak terim: "{term}"

Seviye talimatı: {level_instruction}

KURALLAR:
- SADECE bu terimin genel/yaygın kabul görmüş tanımına dayan, uydurma bilgi verme.
- Terim belirsizse veya birden fazla anlamı varsa, teknoloji/elektronik bağlamındaki en yaygın
  anlamını esas al.
- Terim gerçekten teknoloji/elektronik ile ilgili değilse bunu kibarca belirt, uydurma bir
  teknoloji tanımı UYDURMA.
- Yalnızca açıklamayı yaz, "İşte açıklama:" gibi giriş cümleleri kullanma.
- Ayrıca bu terimle ilgili (varsa) 2-4 ilişkili terim öner (örn. "RAM" için "ROM", "Depolama",
  "Bellek Hızı" gibi).

ÇOK ÖNEMLİ: Cevabını SADECE geçerli bir JSON nesnesi olarak ver, başka hiçbir açıklama ekleme.
Tam olarak şu formatta:
{{"explanation": "<string>", "category": "<kısa kategori adı, örn. 'Donanım'|'Ekran'|'Bağlantı'|'Yazılım' vb.>", "related_terms": ["<string>", ...]}}"""
