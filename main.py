from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.ai import cache
from app.ai.client import generate
from app.ai.prompts.article_analyze import ARTICLE_ANALYZE_SYSTEM_PROMPT
from app.ai.prompts.compare import COMPARE_SYSTEM_PROMPT
from app.ai.prompts.followup import FOLLOWUP_SYSTEM_PROMPT
from app.ai.prompts.general_chat import GENERAL_CHAT_SYSTEM_PROMPT
from app.ai.prompts.parse import CATEGORY_TEMPLATES, build_parse_prompt
from app.ai.prompts.recommend import SYSTEM_PROMPT

load_dotenv()

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
