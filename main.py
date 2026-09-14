from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.ai import cache
from app.ai.client import generate
from app.ai.matching import find_candidates
from app.ai.prompts.article_analyze import ARTICLE_ANALYZE_SYSTEM_PROMPT
from app.ai.prompts.compare import COMPARE_SYSTEM_PROMPT
from app.ai.prompts.compare_sources import build_compare_sources_prompt
from app.ai.prompts.detect_duplicates import build_duplicate_check_prompt
from app.ai.prompts.extract_entities import (
    EXTRACT_ENTITIES_SYSTEM_PROMPT,
    build_product_match_prompt,
)
from app.ai.prompts.followup import FOLLOWUP_SYSTEM_PROMPT
from app.ai.prompts.general_chat import GENERAL_CHAT_SYSTEM_PROMPT
from app.ai.prompts.parse import CATEGORY_TEMPLATES, build_parse_prompt
from app.ai.prompts.recommend import SYSTEM_PROMPT
from app.ai.prompts.score_product import SCORE_PRODUCT_SYSTEM_PROMPT
from app.ai.prompts.suggest_article_meta import SUGGEST_ARTICLE_META_SYSTEM_PROMPT
from app.ai.prompts.verify_article import VERIFY_ARTICLE_SYSTEM_PROMPT

# Çalışma dizini (cwd) nereden başlatılırsa başlatılsın (npm --prefix,
# farklı bir launch config, vb.) her zaman comparaai-ai/.env'i bul.
load_dotenv(Path(__file__).resolve().parent / ".env")

app = FastAPI(title="ComparaAI - AI Danışman Servisi")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class FollowupRequest(BaseModel):
    products: list["Product"]
    question: str


@app.post("/followup")
def followup(request: FollowupRequest):
    products_text = "\n".join(
        [
            f"- {p.name} ({p.brand}), Özellikler: {p.specs}"
            for p in request.products
        ]
    )

    prompt = f"""Önerilen ürünler:
{products_text}

Kullanıcının takip sorusu: "{request.question}\""""

    answer = generate(
        prompt,
        system_instruction=FOLLOWUP_SYSTEM_PROMPT,
        feature="followup",
    )

    return {"answer": answer}


class Product(BaseModel):
    id: str
    name: str
    brand: str
    price: float | None = None
    specs: dict


class RecommendationRequest(BaseModel):
    products: list[Product]
    budget: float | None = None
    priority: str | None = None


@app.get("/")
def health_check():
    return {"status": "ComparaAI AI servisi çalışıyor"}


class DetectCategoryRequest(BaseModel):
    message: str
    categories: str  # "slug:isim, slug:isim, ..." formatında


class DetectCategoryResponse(BaseModel):
    category_slug: str | None = None


@app.post("/detect-category", response_model=DetectCategoryResponse)
def detect_category(request: DetectCategoryRequest):
    prompt = f"""Kullanıcının mesajı: "{request.message}"

Mevcut kategoriler (slug:isim formatında): {request.categories}

Kullanıcının mesajından hangi kategoriyi kastettiğini SADECE bu listeden bul.
Sadece kategorinin "slug" değerini döndür, başka hiçbir şey yazma.
Eğer hiçbiri uymuyorsa veya belirsizse, sadece "null" yaz."""

    raw = generate(prompt, feature="detect-category").strip().strip("`").strip('"').strip()
    if raw.lower() == "null" or not raw:
        return DetectCategoryResponse(category_slug=None)
    return DetectCategoryResponse(category_slug=raw)


class GeneralChatRequest(BaseModel):
    message: str


class GeneralChatResponse(BaseModel):
    answer: str


@app.post("/general-chat", response_model=GeneralChatResponse)
def general_chat(request: GeneralChatRequest):
    answer = generate(
        request.message,
        system_instruction=GENERAL_CHAT_SYSTEM_PROMPT,
        feature="general-chat",
    )
    return GeneralChatResponse(answer=answer)


@app.post("/recommend")
def recommend(request: RecommendationRequest):
    cache_key = cache.make_cache_key(
        "recommend",
        {
            "product_ids": sorted([p.id for p in request.products]),
            "budget": request.budget,
            "priority": request.priority,
        },
    )

    cached = cache.get_cached(cache_key)
    if cached:
        return {**cached, "cached": True}

    products_text = "\n".join(
        [
            f"- {p.name} ({p.brand}), Özellikler: {p.specs}"
            for p in request.products
        ]
    )

    user_context = f"Kullanıcının önceliği: {request.priority}\n" if request.priority else ""

    prompt = f"""{user_context}
Aşağıdaki ürünler arasından kullanıcıya en uygun olanını/olanlarını gerekçeli şekilde öner:

{products_text}"""

    answer = generate(prompt, system_instruction=SYSTEM_PROMPT, feature="recommend")

    result = {"recommendation": answer}
    cache.set_cached(cache_key, result)
    return {**result, "cached": False}


class CompareRequest(BaseModel):
    products: list[Product]


@app.post("/compare")
def compare(request: CompareRequest):
    if len(request.products) < 2:
        return {"error": "Karşılaştırma için en az 2 ürün gerekli."}

    cache_key = cache.make_cache_key(
        "compare", {"product_ids": sorted([p.id for p in request.products])}
    )

    cached = cache.get_cached(cache_key)
    if cached:
        return {**cached, "cached": True}

    products_text = "\n".join(
        [
            f"- {p.name} ({p.brand}), Özellikler: {p.specs}"
            for p in request.products
        ]
    )

    prompt = f"""Aşağıdaki ürünleri detaylı şekilde karşılaştır:

{products_text}"""

    answer = generate(prompt, system_instruction=COMPARE_SYSTEM_PROMPT, feature="compare")

    result = {"comparison": answer}
    cache.set_cached(cache_key, result)
    return {**result, "cached": False}


# --- Serbest metinden yapılandırılmış filtre çıkarma (parse) ---


class ParseRequest(BaseModel):
    category_type: str
    message: str
    known_brands: list[str] = []


class ParsedIntent(BaseModel):
    segment: str | None = None  # "ekonomik" | "orta" | "ust"
    priority: str | None = None
    usage: str | None = None
    brand: str | None = None
    price_insistence: bool = False  # kullanici israrla kesin fiyat/TL istiyor mu
    needs_clarification: bool = False
    clarification_question: str | None = None


@app.post("/parse", response_model=ParsedIntent)
def parse_intent(request: ParseRequest):
    template = CATEGORY_TEMPLATES.get(request.category_type)
    if not template:
        return ParsedIntent(
            needs_clarification=True,
            clarification_question="Bu kategori için henüz destek yok.",
        )

    priorities_list = ", ".join(template["priorities"])
    usage_list = ", ".join(template["usage"])
    brands_list = ", ".join(request.known_brands) if request.known_brands else "belirtilmedi"

    parse_prompt = build_parse_prompt(request.message, priorities_list, usage_list, brands_list)

    raw_text = generate(parse_prompt, feature="parse").strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        return ParsedIntent.model_validate_json(raw_text)
    except Exception:
        return ParsedIntent(
            needs_clarification=True,
            clarification_question="Ekonomik, orta sınıf yoksa üst segment bir ürün mü arıyorsunuz? Sizin için en önemli özellik nedir?",
        )


# --- Haber Analiz AI ---


class ArticleAnalyzeRequest(BaseModel):
    title: str
    content: str


class ArticleAnalyzeResponse(BaseModel):
    summary: str
    importance: str  # "dusuk" | "orta" | "yuksek" | "kritik"
    why_it_matters: str
    who_it_affects: str


@app.post("/analyze-article", response_model=ArticleAnalyzeResponse)
def analyze_article(request: ArticleAnalyzeRequest):
    cache_key = cache.make_cache_key(
        "analyze-article",
        {"title": request.title, "content": request.content},
    )

    cached = cache.get_cached(cache_key)
    if cached:
        return ArticleAnalyzeResponse(**cached)

    prompt = f"""Haber başlığı: {request.title}

Haber içeriği:
{request.content}"""

    raw_text = generate(
        prompt,
        system_instruction=ARTICLE_ANALYZE_SYSTEM_PROMPT,
        feature="analyze-article",
    ).strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        result = ArticleAnalyzeResponse.model_validate_json(raw_text)
    except Exception:
        result = ArticleAnalyzeResponse(
            summary="Bu haber için özet oluşturulamadı.",
            importance="orta",
            why_it_matters="Analiz şu anda yapılamadı.",
            who_it_affects="Belirlenemedi.",
        )

    cache.set_cached(cache_key, result.model_dump())
    return result


# --- Faz 3 P0: AI Ürün Skoru ---


class ScoreProductRequest(BaseModel):
    id: str
    name: str
    brand: str
    category: str
    price: float | None = None
    specs: dict


class ScoreProductResponse(BaseModel):
    overall_score: float
    performance_score: float | None = None
    camera_score: float | None = None
    battery_score: float | None = None
    software_score: float | None = None
    value_score: float | None = None
    use_case_score: dict | None = None
    future_proof_score: float | None = None
    ai_summary: str
    best_for: list[str] = []
    not_for: list[str] = []
    weaknesses: list[str] = []
    suggested_segment: str | None = None


@app.post("/score-product", response_model=ScoreProductResponse)
def score_product(request: ScoreProductRequest):
    price_line = f"Fiyat: {request.price} TL\n" if request.price else ""

    prompt = f"""Ürün: {request.name} ({request.brand})
Kategori: {request.category}
{price_line}Özellikler: {request.specs}

Bu ürünü değerlendir ve puanla."""

    raw_text = generate(
        prompt,
        system_instruction=SCORE_PRODUCT_SYSTEM_PROMPT,
        feature="score-product",
    ).strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        return ScoreProductResponse.model_validate_json(raw_text)
    except Exception:
        return ScoreProductResponse(
            overall_score=50,
            ai_summary="Bu ürün için AI değerlendirmesi şu anda oluşturulamadı.",
        )


# --- Faz 2: Haberden bilgi çıkarma (NER) + Haber<->Ürün bağlantısı ---


class KnownProduct(BaseModel):
    id: str
    name: str
    brand: str


class ExtractEntitiesRequest(BaseModel):
    title: str
    content: str
    known_products: list[KnownProduct] = []


class ExtractedEntity(BaseModel):
    entity_type: str  # 'company' | 'product' | 'technology'
    entity_name: str
    product_id: str | None = None
    confidence: float | None = None


class ExtractEntitiesResponse(BaseModel):
    entities: list[ExtractedEntity]


def _match_product_for_entity(
    entity_name: str, known_products: list[KnownProduct]
) -> tuple[str | None, float | None]:
    """Fuzzy match + (gerekirse) AI doğrulama ile entity'yi bir Product.id'ye bağlar."""
    if not known_products:
        return None, None

    candidates = find_candidates(
        entity_name,
        [{"id": p.id, "name": p.name, "brand": p.brand} for p in known_products],
    )

    if not candidates:
        return None, None

    # Tek ve çok güçlü bir eşleşme varsa AI doğrulamasına gerek yok.
    if len(candidates) == 1 and candidates[0][1] >= 0.85:
        return candidates[0][0]["id"], candidates[0][1]

    # Belirsiz/çoklu adaylarda Gemini'ye doğrulat.
    verify_prompt = build_product_match_prompt(
        entity_name,
        [
            {"id": c["id"], "label": f"{c['brand']} {c['name']}"}
            for c, _score in candidates
        ],
    )
    raw = generate(verify_prompt, feature="extract-entities-verify").strip().strip("`").strip('"').strip()

    if raw.lower() == "none":
        return None, None

    for candidate, score in candidates:
        if candidate["id"] == raw:
            return candidate["id"], score

    return None, None


@app.post("/extract-entities", response_model=ExtractEntitiesResponse)
def extract_entities(request: ExtractEntitiesRequest):
    prompt = f"""Haber başlığı: {request.title}

Haber içeriği:
{request.content}"""

    raw_text = generate(
        prompt,
        system_instruction=EXTRACT_ENTITIES_SYSTEM_PROMPT,
        feature="extract-entities",
    ).strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        raw_entities = ExtractEntitiesResponse.model_validate_json(
            f'{{"entities": {raw_text}}}'
        ).entities
    except Exception:
        return ExtractEntitiesResponse(entities=[])

    resolved: list[ExtractedEntity] = []
    for entity in raw_entities:
        product_id, confidence = (None, None)
        if entity.entity_type == "product":
            product_id, confidence = _match_product_for_entity(
                entity.entity_name, request.known_products
            )
        resolved.append(
            ExtractedEntity(
                entity_type=entity.entity_type,
                entity_name=entity.entity_name,
                product_id=product_id,
                confidence=confidence,
            )
        )

    return ExtractEntitiesResponse(entities=resolved)


# --- Faz 2: Duplicate Haber Tespiti ---


class DuplicateCandidate(BaseModel):
    id: str
    title: str
    summary: str


class DetectDuplicatesRequest(BaseModel):
    title: str
    summary: str
    candidates: list[DuplicateCandidate] = []


class DuplicateMatch(BaseModel):
    article_id: str
    similarity_score: float
    reason: str


class DetectDuplicatesResponse(BaseModel):
    duplicates: list[DuplicateMatch]


@app.post("/detect-duplicates", response_model=DetectDuplicatesResponse)
def detect_duplicates(request: DetectDuplicatesRequest):
    if not request.candidates:
        return DetectDuplicatesResponse(duplicates=[])

    prompt = build_duplicate_check_prompt(
        request.title,
        request.summary,
        [{"id": c.id, "title": c.title, "summary": c.summary} for c in request.candidates],
    )

    raw_text = generate(prompt, feature="detect-duplicates").strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        return DetectDuplicatesResponse.model_validate_json(
            f'{{"duplicates": {raw_text}}}'
        )
    except Exception:
        return DetectDuplicatesResponse(duplicates=[])


# --- Faz 2: AI Editör (başlık/SEO/etiket önerisi) ---


class SuggestArticleMetaRequest(BaseModel):
    title: str = ""
    content: str


class SuggestArticleMetaResponse(BaseModel):
    title_suggestions: list[str] = []
    seo_meta_description: str = ""
    tags: list[str] = []


@app.post("/suggest-article-meta", response_model=SuggestArticleMetaResponse)
def suggest_article_meta(request: SuggestArticleMetaRequest):
    title_line = f"Mevcut başlık (varsa): {request.title}\n" if request.title else ""
    prompt = f"""{title_line}Haber içeriği:
{request.content}"""

    raw_text = generate(
        prompt,
        system_instruction=SUGGEST_ARTICLE_META_SYSTEM_PROMPT,
        feature="suggest-article-meta",
    ).strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        return SuggestArticleMetaResponse.model_validate_json(raw_text)
    except Exception:
        return SuggestArticleMetaResponse()


# --- Faz 2: AI Haber Doğrulama Yardımcısı ---


class VerifyArticleRequest(BaseModel):
    title: str
    content: str


class VerifyIssue(BaseModel):
    issue_type: str  # 'celiski' | 'abartili_iddia' | 'kaynak_belirsiz'
    excerpt: str
    explanation: str
    suggestion: str


class VerifyArticleResponse(BaseModel):
    issues: list[VerifyIssue]


@app.post("/verify-article", response_model=VerifyArticleResponse)
def verify_article(request: VerifyArticleRequest):
    prompt = f"""Haber başlığı: {request.title}

Haber içeriği:
{request.content}"""

    raw_text = generate(
        prompt,
        system_instruction=VERIFY_ARTICLE_SYSTEM_PROMPT,
        feature="verify-article",
    ).strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        return VerifyArticleResponse.model_validate_json(f'{{"issues": {raw_text}}}')
    except Exception:
        return VerifyArticleResponse(issues=[])


# --- Faz 2: Çoklu Kaynak Haber Analizi ---


class SourceArticle(BaseModel):
    author: str | None = None
    title: str
    content: str


class CompareSourcesRequest(BaseModel):
    articles: list[SourceArticle]


class CompareSourcesResponse(BaseModel):
    consensus: list[str] = []
    differences: list[str] = []
    emphasis_notes: list[str] = []


@app.post("/compare-sources", response_model=CompareSourcesResponse)
def compare_sources(request: CompareSourcesRequest):
    if len(request.articles) < 2:
        return CompareSourcesResponse()

    prompt = build_compare_sources_prompt(
        [
            {"author": a.author, "title": a.title, "content": a.content}
            for a in request.articles
        ]
    )

    raw_text = generate(prompt, feature="compare-sources").strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        return CompareSourcesResponse.model_validate_json(raw_text)
    except Exception:
        return CompareSourcesResponse()
