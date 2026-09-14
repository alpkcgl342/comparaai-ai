"""'/parse' ve '/detect-category' endpoint'leri için şablon veriler.

Bu iki endpoint sabit bir "system_instruction" kullanmıyor; prompt'u her istekte
kategoriye göre dinamik olarak main.py içinde kuruyor. Kategori bazlı öncelik/
kullanım listeleri değişmediği için burada tutuluyor.
"""

TELEFON_PRIORITIES = ["batarya", "kamera", "performans", "fiyat_performans"]
TELEFON_USAGE = ["gunluk", "oyun", "sosyal_medya_fotograf", "is"]
LAPTOP_PRIORITIES = ["tasinabilirlik", "performans", "pil_omru", "ekran_kalitesi", "fiyat_performans"]
LAPTOP_USAGE = ["ofis", "oyun", "tasarim_video", "yazilim_gelistirme", "gunluk"]
MASAUSTU_PRIORITIES = ["performans", "oyun_gucu", "sessizlik", "fiyat_performans"]
MASAUSTU_USAGE = ["ofis", "oyun", "tasarim_video", "yazilim_gelistirme"]
PC_PARCASI_PRIORITIES = ["performans", "uyumluluk", "enerji_verimliligi", "fiyat_performans"]
PC_PARCASI_USAGE = ["oyun", "tasarim_video", "yazilim_gelistirme", "genel"]

CATEGORY_TEMPLATES = {
    "telefon": {"priorities": TELEFON_PRIORITIES, "usage": TELEFON_USAGE},
    "laptop": {"priorities": LAPTOP_PRIORITIES, "usage": LAPTOP_USAGE},
    "masaustu": {"priorities": MASAUSTU_PRIORITIES, "usage": MASAUSTU_USAGE},
    "pc-parcalari": {"priorities": PC_PARCASI_PRIORITIES, "usage": PC_PARCASI_USAGE},
}

SEGMENTS = ["ekonomik", "orta", "ust"]


def build_parse_prompt(message: str, priorities_list: str, usage_list: str, brands_list: str) -> str:
    return f"""Kullanıcının mesajı: "{message}"

Bu mesajı aşağıdaki alanlara ayrıştır. Kullanıcının yazım hatalarını (örn. "zamsungg" -> "Samsung") doğru şekilde yorumla.

- Kullanıcının cümlesini yalnızca kelime eşleşmesiyle değil, cümlenin tamamındaki anlamı dikkate alarak yorumla.
- Kullanıcının yazım hatalarını, harf tekrarlarını, eksik harfleri, Türkçe karakter hatalarını ve konuşma dilini anlamına göre düzelt.
  Örneğin:
  "zamsungg" -> "Samsung"
  "samsng" -> "Samsung"
  "ıphone" -> "iPhone"
  "iphon" -> "iPhone"

- Kullanıcı bir marka adını farklı bir yazımla ifade ederse, brands_list içindeki en yakın gerçek markayı seç.
- Kullanıcı birden fazla marka belirtirse brand alanında yalnızca brands_list formatının izin verdiği şekilde
  tek bir marka seç. Birden fazla marka desteklenmiyorsa ilk açıkça belirtilen markayı tercih et.
- Kullanıcı marka belirtmiyorsa brand=null bırak.

- Kullanıcının doğrudan kullandığı kelimelerin yanında anlam bakımından eşdeğer ifadeleri de dikkate al.
  Örneğin:
  "cebimi yakmasın", "çok para vermek istemiyorum", "uygun fiyatlı" -> ekonomik
  "fiyat performans", "çok uçmasın", "makul bir şey" -> orta
  "en üstünü istiyorum", "parasını düşünme", "en güçlü olsun" -> ust

- Kullanıcı bütçe konusunda hem düşük hem yüksek seviyeyi ifade eden çelişkili ifadeler kullanırsa,
  cümlenin son ve en açık bütçe tercihini esas al.
  Örneğin "çok pahalı olmasın ama en iyisi olsun" gibi bir durumda yalnızca kelimelere bakma;
  kullanıcının asıl tercihinin belirsiz olduğunu değerlendir ve mümkünse segment=null bırak.

- Kullanıcı yalnızca bir ürünün pahalı veya ucuz olduğunu söylüyorsa bunu otomatik olarak kullanıcının
  istediği segment olarak kabul etme.
  Örneğin "X pahalı mı?" ifadesi kullanıcının "ust" segment istediği anlamına gelmez.

- Kullanıcı "bütçem 20 bin", "20 bine kadar", "20 bin civarı", "20 bin TL'yi geçmesin" gibi
  kesin veya yaklaşık bir rakam verirse bu rakamı segment sınıflandırması için kullanabilirsin;
  ancak segment alanına kesin TL rakamı yazma ve kullanıcının verdiği rakamı başka bir alana aktarma.

- Kullanıcı "X TL'ye kadar" diyorsa bunun bir bütçe sınırı olduğunu anla.
  Kullanıcı "X TL verebilirim" diyorsa bunu bütçe sinyali olarak değerlendir.
  Ancak mevcut üç segmentten hangisine karşılık geldiği güvenilir şekilde belirlenemiyorsa
  segment=null bırak.

- Segment sınıflandırmasında yalnızca kullanıcının açıkça verdiği bütçe sinyallerini ve sistem tarafından
  tanımlanan segment anlamlarını kullan. Rastgele veya kişisel fiyat varsayımı yapma.

- priority ve usage alanlarında yalnızca verilen listelerdeki değerleri kullan.
  Kullanıcının ifadesi listedeki bir değere yakın anlam taşıyorsa onu eşleştir.
  Ancak listede karşılığı olmayan yeni bir değer üretme.

- Kullanıcı birden fazla öncelik veya kullanım amacı belirtiyorsa, priority ve usage alanlarının
  yalnızca tek değer kabul ettiği durumda kullanıcının en açık şekilde vurguladığı veya cümlenin
  ana amacını oluşturan değeri seç.

- Kullanıcı "kamera önemli ama oyun da oynarım" gibi birden fazla öncelik belirtiyorsa,
  ana amacı belirlemek için cümlenin tamamını değerlendir.
  Birden fazla değer için kesin bir öncelik belirlenemiyorsa ilgili alanı null bırakmak,
  yanlış bir değer seçmekten daha doğrudur.

- "önceliğim", "benim için önemli", "özellikle", "en çok", "ağırlıklı olarak" gibi ifadelerden
  sonra gelen kriterleri daha güçlü öncelik sinyali olarak değerlendir.

- Kullanıcının geçmiş konuşmasındaki bilgiler parse_prompt'a dahil edilmediyse geçmiş konuşmayı
  varsayma. Yalnızca mevcut input mesajında bulunan bilgileri ayrıştır.

- Kullanıcı "en iyi", "en güçlü", "performanslı" gibi ifadeler kullanıyorsa:
  Eğer priority_list içinde bunlara karşılık gelen bir değer varsa onu seç.
  Yoksa yeni bir priority değeri üretme ve priority=null bırak.
  "en iyi" ifadesini otomatik olarak "ust" segment olarak kabul etme; yalnızca bütçe/segment anlamında
  kullanıldığı açıkça anlaşılıyorsa ust olarak değerlendir.

- Kullanıcı "ucuz olsun", "fazla para vermek istemiyorum" gibi ifadeler kullanıyorsa ekonomik segment;
  "fiyat performans", "makul", "orta karar" gibi ifadeler kullanıyorsa orta segment;
  "en üst seviye", "en güçlü", "premium", "parasına bakmam" gibi ifadeler kullanıyorsa ust segment
  olarak değerlendir.

- Kullanıcı yalnızca marka söylüyorsa segment ve priority alanlarını null bırakabilirsin.
  Örneğin "Samsung telefon bakıyorum" -> brand="Samsung", diğer uygun alanlar null.

- Kullanıcı yalnızca kullanım amacını söylüyorsa bunu usage alanına aktar.
  Örneğin "oyun için bir telefon istiyorum" -> usage listesinde karşılığı varsa ilgili değeri seç.

- Kullanıcı yalnızca önceliğini söylüyorsa bunu priority alanına aktar.
  Örneğin "kamerası benim için önemli" -> priority listesinde karşılığı varsa ilgili değeri seç.

- Kullanıcı hiçbir kategori, bütçe, öncelik, kullanım amacı veya marka belirtmiyorsa mevcut bilgileri
  uydurma ve ilgili alanları null bırak.

- needs_clarification kararında yalnızca segment ve priority alanlarına bakma.
  Kullanıcının usage veya brand gibi başka anlamlı bir bilgisi varsa bunu dikkate al.
  Ancak mevcut sistem akışında segment ve priority ikisi de null ise needs_clarification=true kuralını
  koru.

- needs_clarification=true olduğunda clarification_question:
  • kısa olmalı,
  • doğal olmalı,
  • kullanıcıdan kesin TL rakamı istememeli,
  • mümkünse hem bütçe segmentini hem de kullanım önceliğini anlamaya yardımcı olmalı.

  Örnek:
  "Daha ekonomik, orta sınıf veya üst segment bir seçenek mi arıyorsunuz? Sizin için en önemli
  özellik hangisi?"

- Kullanıcı zaten yeterli bilgi verdiyse gereksiz clarification_question üretme.
- needs_clarification=false olduğunda clarification_question kesinlikle null olmalı.
- needs_clarification=true olduğunda clarification_question kesinlikle null olmamalı.

- price_insistence yalnızca kullanıcının gerçekten kesin fiyat talep ettiği durumlarda true olmalıdır.
  "Fiyatı uygun mu?", "bütçeme uygun mu?", "pahalı mı?", "ekonomik mi?" gibi göreceli sorular
  price_insistence=true değildir.
- "tam olarak kaç TL?", "net fiyat nedir?", "bana kesin fiyatı söyle", "kaç TL olduğunu açıkça söyle"
  gibi ifadeler kesin fiyat talebi olduğundan price_insistence=true yapılmalıdır.
- Kullanıcı yalnızca bir TL rakamı yazdı diye price_insistence=true yapma.
  Örneğin "20 bin TL bütçem var" -> price_insistence=false.
- Kullanıcı fiyatı bir kez sordu ancak kesin rakam konusunda ısrarcı değilse price_insistence=false bırak.

ÇOK ÖNEMLİ: Cevabını SADECE geçerli bir JSON nesnesi olarak ver, başka hiçbir açıklama/metin ekleme.
Tam olarak şu formatta:
{{"segment": <string veya null>, "priority": <string veya null>, "usage": <string veya null>, "brand": <string veya null>, "price_insistence": <true/false>, "needs_clarification": <true/false>, "clarification_question": <string veya null>}}"""
