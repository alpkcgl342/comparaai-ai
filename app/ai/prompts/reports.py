"""Faz 6 — Trend/Rapor özellikleri için promptlar.

- Şirket AI Analizi (/analyze-company)
- Günlük/Haftalık Teknoloji Raporu (/generate-report)
- "Bu teknoloji neyi değiştirecek?" (/technology-impact)

Trend TESPİTİ burada değil — o saf SQL (bkz. ComparaAI backend
ReportService.trending), AI çağrısı gerektirmiyor. Bu dosyadaki
promptlar sadece SQL'in bulduğu sinyale AI yorumu eklemek için.
"""


def build_company_analysis_prompt(
    company_name: str, articles: list[dict], products: list[dict]
) -> str:
    articles_text = (
        "\n".join(f'- "{a["title"]}": {a.get("summary") or ""}' for a in articles)
        or "(bu şirketle ilgili haber bulunamadı)"
    )
    products_text = (
        "\n".join(f'- {p["name"]}: {p.get("specs")}' for p in products)
        or "(bu şirkete ait ürün bulunamadı)"
    )

    return f"""Şirket: {company_name}

Bu şirketle ilgili son haberler:
{articles_text}

Bu şirkete ait ürünlerimiz:
{products_text}

GÖREVİN:
Yukarıdaki verilere dayanarak "{company_name}" hakkında kısa bir analiz özeti hazırla:
- Son dönemde öne çıkan gelişmeler neler (varsa)
- Ürün portföyünün genel karakteri (varsa ürün verisi)
- Kullanıcılar için dikkat çekici bir çıkarım (varsa)

KURALLAR:
- SADECE verilen haber ve ürün verilerine dayan, uydurma bilgi/rakam/olay ekleme.
- Veri çok azsa veya hiç yoksa bunu dürüstçe belirt, doldurmaya çalışma.
- Kesin/abartılı ifadelerden kaçın, ihtiyatlı bir dil kullan.
- 4-6 cümlelik, akıcı bir paragraf yaz (madde madde değil).

ÇOK ÖNEMLİ: Cevabını SADECE geçerli bir JSON nesnesi olarak ver.
Format: {{"analysis": "<string>"}}"""


def build_generate_report_prompt(
    report_type: str,
    articles: list[dict],
    trending_entities: list[dict],
) -> str:
    articles_text = "\n".join(
        f'- [{a.get("aiImportance") or "belirsiz"}] "{a["title"]}": {a.get("summary") or ""}'
        for a in articles
    ) or "(bu dönemde haber yok)"

    trending_text = "\n".join(
        f'- {e["entityName"]} ({e["entityType"]}): {e["mentionCount"]} haberde geçti'
        for e in trending_entities
    ) or "(belirgin bir trend yok)"

    period_label = "GÜNLÜK" if report_type == "daily" else "HAFTALIK"

    return f"""{period_label} TEKNOLOJİ RAPORU hazırlıyorsun.

Bu dönemin haberleri (önem derecesiyle):
{articles_text}

Bu dönemde öne çıkan (trend) konular:
{trending_text}

GÖREVİN:
1. "title": Rapor için kısa, açıklayıcı bir başlık (örn. "15-21 Eylül Teknoloji Özeti").
2. "highlights": Bu dönemin en önemli 3-5 gelişmesi, her biri 1 cümlelik özet (madde listesi).
3. "trend_commentary": Trend olan konular hakkında 2-3 cümlelik bir yorum — neden öne çıktıklarına
   dair kısa bir gözlem (spekülasyon değil, verilen haberlere dayanan bir gözlem).
4. "social_summary": Bu raporun sosyal medyada paylaşılabilecek, 2-3 cümlelik, dikkat çekici ama
   abartısız bir özeti (emoji kullanabilirsin, ölçülü).

KURALLAR:
- SADECE verilen haber verilerine dayan, uydurma olay/rakam ekleme.
- Veri azsa (örn. hiç haber yoksa) bunu dürüstçe belirt, "highlights" boş kalabilir.
- Sansasyonel/abartılı dilden kaçın.

ÇOK ÖNEMLİ: Cevabını SADECE geçerli bir JSON nesnesi olarak ver.
Format: {{"title": "<string>", "highlights": ["<string>", ...], "trend_commentary": "<string>", "social_summary": "<string>"}}"""


def build_technology_impact_prompt(technology_name: str, articles: list[dict]) -> str:
    articles_text = "\n".join(
        f'- "{a["title"]}": {a.get("summary") or ""}' for a in articles
    ) or "(bu konuyla ilgili haber bulunamadı)"

    return f"""Konu: "{technology_name}"

Bu konuyla ilgili haberler:
{articles_text}

GÖREVİN:
"{technology_name}" konusunun (teknoloji/ürün/trend) kullanıcılar ve sektör için ne anlama
geldiğine, kısa-orta vadede neyi değiştirebileceğine dair dengeli bir analiz yaz.

KURALLAR:
- SADECE verilen haberlere dayan; gelecekle ilgili net garantiler verme, "olabilir",
  "beklenebilir" gibi ihtiyatlı ifadeler kullan.
- Veri yetersizse (haber azsa/yoksa) bunu dürüstçe belirt, kapsamlı bir tahmin uydurma.
- Sansasyonel ifadelerden ("çığır açacak", "her şeyi değiştirecek") kaçın; sadece haberler
  gerçekten bunu destekliyorsa kullan.
- 5-7 cümlelik bir paragraf yaz.

ÇOK ÖNEMLİ: Cevabını SADECE geçerli bir JSON nesnesi olarak ver.
Format: {{"analysis": "<string>"}}"""
