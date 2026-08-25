import json
import os
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote
import urllib.request
import urllib.error

# -- Sabitler ---------------------------------------------------------------
CATALOG_URL = "https://vavoo.to/mediahubmx-catalog.json"
GROUP = "Turkey"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
M3U_FILE = os.path.join(SCRIPT_DIR, "nernur.txt")
FETCH_TIMEOUT_SECONDS = 20
MAX_RETRIES = 5

# -- Proxy Ayrıştırma Ve Temizleme Fonksiyonu ------------------------------
def parse_proxies(env_val: Optional[str]) -> List[str]:
    if not env_val or not env_val.strip():
        return []

    tokens = re.split(r"[\s,]+", env_val.strip())
    proxies = []
    for p in tokens:
        clean_p = p.rstrip("/")
        if clean_p.startswith("http://") or clean_p.startswith("https://"):
            proxies.append(clean_p)
    return proxies


ENV_PROXIES = parse_proxies(os.getenv("PROXY_BASE"))

# Yedek liste
FALLBACK_PROXIES = [
    "https://halil.bilalkamera20.workers.dev",
    "https://adam.bilalkamera20.workers.dev",
    "https://ner.bilalkamera20.workers.dev",
    "https://nur.bilalkamera20.workers.dev",
    "https://vavoo-iptv-proxy.bilalkamera20.workers.dev",
    "https://nernur.bilalkamera20.workers.dev",
    "https://balkica.bilalkamera20.workers.dev",
    "https://bilal.bilalkamera20.workers.dev",
    "https://vav20.bilalkamera20.workers.dev",
    "https://hmeb.bilalkamera20.workers.dev",
]

PROXY_LIST = ENV_PROXIES if len(ENV_PROXIES) > 0 else FALLBACK_PROXIES
proxy_index = 0

HEADERS = {
    "content-type": "application/json; charset=utf-8",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9,tr;q=0.8",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "origin": "https://vavoo.to",
    "referer": "https://vavoo.to/live",
    "dnt": "1",
    "sec-ch-ua": '"Not=A?Brand";v="99", "Google Chrome";v="151", "Chromium";v="151"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    ),
}


def build_body(cursor: Optional[str]) -> Dict[str, Any]:
    return {
        "language": "en",
        "region": "ALL",
        "catalogId": "iptv",
        "id": "",
        "adult": False,
        "search": "",
        "sort": "name",
        "filter": {"group": GROUP},
        "cursor": cursor,
    }


def fetch_page(cursor: Optional[str]) -> Dict[str, Any]:
    body_data = json.dumps(build_body(cursor)).encode("utf-8")
    last_err = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                CATALOG_URL, data=body_data, headers=HEADERS, method="POST"
            )
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as res:
                if res.status != 200:
                    raise Exception(f"HTTP {res.status}")

                raw_response = res.read().decode("utf-8")
                data = json.loads(raw_response)

                if isinstance(data, dict) and data.get("error"):
                    raise Exception(f"Vavoo hatası: {data['error']}")

                return data
        except Exception as err:
            last_err = err
            wait = attempt
            print(
                f"Deneme {attempt}/{MAX_RETRIES} başarısız ({err}). {wait}sn sonra tekrar deneniyor..."
            )
            time.sleep(wait)

    raise last_err if last_err else Exception("Bilinmeyen istek hatası.")


def fetch_all() -> List[Dict[str, Any]]:
    items = []
    cursor = None
    page = 0
    MAX_PAGES = 200

    while True:
        page += 1
        data = fetch_page(cursor)

        page_items = data.get("items") if isinstance(data, dict) else None
        if isinstance(page_items, list) and len(page_items) > 0:
            items.extend(page_items)

        print(
            f"Sayfa {page}: {len(page_items) if page_items else 0} kanal çekildi, "
            f"nextCursor={data.get('nextCursor') if isinstance(data, dict) else 'null'}"
        )

        cursor = data.get("nextCursor") if isinstance(data, dict) else None

        if page >= MAX_PAGES:
            print(f"Maksimum sayfa sınırına ulaşıldı ({MAX_PAGES}).")
            break

        if not cursor:
            break

    return items


# -- Temizleme ve Kategorizasyon Yardımcıları (PHP Birebir Port) ------------

def clean_channel_name(name: Optional[str]) -> str:
    if not name:
        return "Bilinmeyen Kanal"

    s = str(name)
    # 1. Baştaki "4K TR:", "TR:", "4K TR :" gibi ifadeleri kaldırır
    s = re.sub(r"^\s*(?:4K\s*)?TR\s*:\s*", "", s, flags=re.IGNORECASE)
    # 2. Sondaki veya kelime aralarındaki .b, .c, .s gibi nokta uzantılarını kaldırır
    s = re.sub(r"\s*\.[bcs]\b", "", s, flags=re.IGNORECASE)
    # 3. Çözünürlük ve yayın kalitesi etiketlerini temizler
    s = re.sub(r"\s+(?:4K|UHD|FHD|HD\+|HD|SD|HEVC|RAW|H265|H\.265|FEED)(?=\s|$)", "", s, flags=re.IGNORECASE)
    # 4. Fazla boşlukları temizler
    s = re.sub(r"\s+", " ", s)

    return s.strip()


def normalize_for_category(name: Optional[str]) -> str:
    s = clean_channel_name(name)

    replacements = [
        (r"\bT RK\b", "TURK"),
        (r"\bT RKIYEM\b", "TURKIYEM"),
        (r"\bBENG\b", "BENGU"),
        (r"\bBENGT\b", "BENGUT"),
        (r"\bAK T\b", "AKIT"),
        (r"\bS NEMA\b", "SINEMA"),
        (r"\bM N KA\b", "MINIKA"),
        (r"\bOCUK\b", "COCUK"),
        (r"\bM Z K\b", "MUZIK"),
        (r"\bS ZC\b", "SOZCU"),
        (r"\bSZC\b", "SOZCU"),
        (r"\bLKE\b", "ULKE"),
        (r"\bYE IL AM\b", "YESILCAM"),
        (r"\bYE IL[ ]?CAM\b", "YESILCAM"),
        (r"\bT[ÜU]RK\b", "TURK"),
    ]

    for pattern, repl in replacements:
        s = re.sub(pattern, repl, s, flags=re.IGNORECASE)

    return s


CATEGORY_RULES = [
    ('TR Radyo', r'\b(RADIO|RADYO)\b|\b(FM|MBAT FM|EFKAR FM|FMTV|F ?M)\b(?!\s*TV)|POWERTURK|POWER FM|SHOW RADYO|ALEM (?:FM|RADYO)|BABA RADYO|KRAL POP RADYO|PAL STATION|X NOSTALJI|RADIO ROCK|STANBUL FM'),
    ('TR Çocuk', r'CARTOON|BOOMERANG|DISNEY|NICK(?:ELODEON|TOONS|JR|JUNIOR|\b)|BABY ?TV|BABYTV|M[İI]?N ?KA|MINIKA|POKEMON|POKÉMON|ANIMATION|ANIMASYON|TRT ?[ÇC]?OCUK|OCUK HD|\bCOCUK\b|\b[ÇC]OCUK\b|BEN ?10|ANGRY BIRDS|CAILLOU|PEPPA|PEPE|HEIDI|SIRINLER|TOM & JERRY|S[ÜU]NGER|SPIDERMAN|BARBIE|PIJAMA|PIRIL|RAFADAN|KELOGLAN|KUKULI|KUKILI|KOSTEBEK|CHICKY|BOOBA|WAKFU|GABBY|TAYO|NILOYA|PISI|LEYLEK|MASAL|CANIM KARDESIM|ADIBESA|MOMO|ALVIN|VIKINGLER|TRANSFORMERS|TROL AVCILARI|SMART COCUK|ILAHI COCUK|CILGIN ORMAN|KRAL SAKIR|SERCE KUS|ITFAYECI SAM|MUFFETIS|MAYMUNLAR|ELIF VE|ELIFIN|MIMOCAN|HAPSUU|RUYA TRENI|MASA KOCAAYI|PAK PIRPIR|LIMON ZEYTIN|GONCA TV|NASREDDIN|SEKER HOCA|SEVIMLI DOSTLAR|PAW PETROL|OSCAR COLLERDE|SL NILOYA|CBEEBIES|DUCK TV|JIM ?JAM|ENGLISH CLUB TV|EBA TV|TAV[SŞ]AN|PATRON BEBEK|D[İI]YARI|BAHA\b|SEF ROKKA|BULMACA KULESI|AKILLI TAV[SŞ]AN|AKLILI|CANIM KARDESIM|DA VINC KIDS|DA VINCI KIDS|DINAMIK ANIMASYON|DREAM ANIMASYON|MAX ANIMASYON|ENO ANIMASYON|BEST ANIMASYON|YILDIZ KIZ|KONU[SŞ]AN TOM|JURASSIC WORLD|MONTAG'),
    ('TR Belgesel', r'DISCOVERY|NATIONAL GEOGRAPHIC|NAT ?GEO|\bHISTORY\b|ANIMAL PLANET|DA VINCI(?! KIDS)|VIASAT|BBC EARTH|LOVE NATURE|TRT BELGESEL|EPIC DRAMA|TARIH TV|TARIM TV|TGRT BELGESEL|INVESTIGATION|DMAX|DOCUBOX|DOCU SCREEN|SCIENCE|\bIZ TV\b|YABAN|OUTDOOR|CHASSE|ANIMAUX|AGRO TV|CIFTCI TV|REDBULL TV|\bTLC\b'),
    ('TR Spor', r'BEIN SPO[RT]{0,3}S?|\bBEIN 1\b|S[- ]?SPORTS?|\bS SPORT\b|SPOR SMART|EUROSPORT|\bNBA\b|TJK TV|TIVIBU ?SPOR|TIVIBUSPOR|TRT SPOR|TABII SPOR|EXXEN SPO[RT]?|\bHT SPOR\b|EKOL SPOR|SPORTS TV|IDMAN TV|GALATASARAY TV|\bFB TV\b|\bGS TV\b|SARAN SPORT|SMART SPOR|\bSPOR\b|\bSPORT\b'),
    ('TR Film', r'SINEMA|S[İI]NEMA|S NEMA|CINEMA|SINEMAX|SINEVIZYON|\bMOVIES?\b|MOVIEMAX|MOVIESMART|BEIN MOVIES|BEIN BOX|BOX OFFICE|\bFX\b|FX HD|YESILCAM|YE ?I ?L ?[ÇC] ?AM|YE ?I ?L ?AM|YEŞ?[İI]LC?AM|GLOBAL BOX|PROTURK|FIX CINEMA|KINGBOX|ARENA BOX|SHOWMAX|SHOW MAX|REAL BOX|SMART BOX|BEST (?:AKSIYON|BILIMKURGU|DRAM|HABABAM|IMBD|KOMEDI|KORKU|LOCA|NETFLIX|SALON|SAVAS|TURK|WESTERN|YESILCAM)|MAX (?:007|AKSIYON|GOLD|ORJINAL|PREMIER|STAR WARS|TURK|VIZYON|WESTERN)|DINAMIK (?:AKSIYON|BILIMKURGU|DRAM|IMBD|KOMEDI|KORKU|TURK|VIZYON|WESTERN|YESILCAM)|DREAM (?:AKSIYON|BEIN OFFICE|BOX|DRAM|KEMAL|KOMEDI|KORKU|LOCA|NETFLIX|SAVAS|WESTERN)|ULTRA (?:AKSIYON|BILIMKURGU|IMBD|KEMAL|KOMEDI|KORKU|TURK)|ENO (?:AKSIYON|VIZYON|WESTERN)|\bLOCA\b|\bSALON\b|\bVIZYON\b|AKSIYON|AKS[İIY]?YON|AKS YON|KOMED[İI]|\bKORKU\b|\bDRAM\b|WESTERN|BILIM ?KURGU|\bSAVAS\b|\bIMBD\b|\bIMDB\b|\bFILM\b|FILMBOX|HORROR|OSCAR|KEMAL SUNAL|\b007\b|\bCINE ?1\b|SIFIR TV|SON C BOOM|\bYERL[İI]\b|SPIDERMAN(?! TV)|ARENA BOX|MOVIE SMART|\bM ?T[UÜ]RK TV\b|\bM TURK TV\b|\bM T RK TV\b'),
    ('TR Dizi', r'SER[İI]ES|\bDIZI\b|BEIN SERIES|D[İI]Z[İI] ?SMART|DIZISMART'),
    ('TR Müzik', r'POWER T[UÜ]RK|POWER ?TV|POWERTURK|POWER (?:DANCE|LOVE|HD)|\bPOWER\b|KRAL POP|KRAL ?TV|\bKRAL\b|TRT M[UÜ]?Z[İI]?K|TRT MUZIK|NR ?1|NUMBER ?1|NUMBER ONE|DAMAR|ARABESK|AKUS ?T[İI]K|AHMET KAYA|IBRAHIM ERKAL|IBRAHIM TATLISES|\bTATLISES\b|ZERRIN OZER|SEZEN AKSU|TARKAN|SELDA BAGCAN|CENGIZ KURTOGLU|MAHSUN KIRMIZIGUL|MUSLUM GURSES|YILDIZ TILBE|FERDI TAYFUR|DURSUN AL|MTV LIVE|VINTAGE MUSIC|RETRO T ?RK|RETRO TURK|T[UÜ]?RK ?E POP|T RK E POP|T RK E KLASIK|SLOW KARADENIZ|\bSLOW\b|\bZARA\b|\bSONER ARICA\b|M[UÜ]Z[İI]K|\bFM TV\b|\bFMTV\b|REDBOX'),
    ('TR Haber', r'\bHABER\b|\bNEWS\b|BLOOMBERG|\bCNN\b|EKOTURK|\bEKO ?T[UÜ]RK\b|\bEKOL\b|A ?PARA|APARA|PARANIN|HALK TV|TELE ?1|SOZCU|S ZC|\bSZC\b|BENGU ?T[UÜ]RK|BENGUTURK|TRT WORLD|\bDHA\b|LIDER HABER|FLASH HABER|MEDYA HABER|GLOBAL HABER|TRABZON HABER|BEIN SPORTS HABER|T[UÜ]RKHABER|HABERT[UÜ]RK|HABERT RK|\bARTI TV\b'),
    ('TR Dini', r'D[İI]YANET|\bAK[İIY]?T\b|MEHTAP|H[İI]LAL|KUDUS|KUDÜS|KUD S|SEMERKAND|LALEGUL|LÂLEGÜL|L[AÂ]LEG[UÜ]L|MERCAN TV|VUSLAT|KARDELEN|DIYAR TV|\bDOST TV\b|\bYOL TV\b|\bKANAL 7\b|HAYAT|HAYIRLI|HZ MERYEM|HZ OMER|HZ YUSUF|MAM EBU|ASHABI KEHF|HASAN VE HUSEYIN|SAT ?7 T[UÜ]RK|TVNET|TRT DIYANET|\bTV ?5\b|\bTV5\b|REHBER|ILAHI|ILKE TV|MESAJ TV|SURELER|T[UÜ]RK ?E MEAL|DURSUN AL ERZINCANLI|YUNUS EMRE|CEM TV|BARBAROS TV|ASLAN TV|TYT TURK|SATRAN[ÇC]|FASIL'),
    ('TR Yaşam', r'24 KITCHEN|GURME|BEIN GURME|LIFESTYLE|\bLIFE TV\b|FASHION|WM TV|EGE ILE GAGA|24 RAW|\bTVEM\b|\bTV EM\b|AUTOMOTO|LINE TV|BILGILENDIRME|WOMAN|TELEGRAM'),
    ('TR Ulusal', r'^24$|\bTRT\b|\bTRT 1\b|\bTRT ?2\b|TRT2|\bTRT 3\b|TRT AVAZ|TRT T[UÜ]RK|TRT TURK|TRT KURD[İI]?|TRT WORLD|TRT 4K|TRT EBA|\bKANAL D\b|\bATV\b|ATV AVRUPA|ATV EUROPA|STAR TV|\bSTAR\b|STAR HD|SHOW TV|SHOW T[UÜ]RK|\bSHOW\b|\bFOX\b|NOW ?TV|\bNOW\b|TV ?8|TV8[.,]5|BEYAZ TV|BEYAZ HD|\bBEYAZ\b|\b360\b|24 TV|\bA2\b|A HABER|A NEWS|A PARA|A SPOR|TV ?100|TV ?4|FLASH TV|TEVE ?2|TEVE2|CNN T[UÜ]RK|CNN TURK|\bKRT\b|ULUSAL KANAL|DREAM T[UÜ]RK|DREAM TURK|\bDREAM TV\b|\bBRT ?[0-9]|\bBRTV\b|EURO ?D|EURO ?STAR|\bNTV\b|EXXEN TV|TIVI ?T[UÜ]RK|TABII|OLAY T[UÜ]RK|OLAY TURK|24 HD|24 HABER|24 KITCHEN|LKE ?TV|[UÜ]LKE ?TV|ULKE ?TV|ULKETV|TV DEN|TVDEN|KANAL AVRUPA|KANAL 7 (?:AVRUPA|EUROPA)|LKE TV|EURO D|EURO STAR|SHOW TV EUROPA|BENGU ?T[UÜ]RK|BENGU TURK|BENGUTURK|TGRT EU|D ?[ĞG] ?N TV|\bTBMM\b|TV NET|\bTV 1\b|TVO TV|BEIN IZ|\bMAX\b'),
    ('TR Yerel', r'ADANA|AD[İI]YAMAN|AFYON|AKSARAY|ALANYA|ANAKKALE|\bANKARA\b|ANKA TV|ANKARA T[UÜ]RKIYEM|ANLIURFA|ANTALYA|\bBURSA\b|ELAZIG|ERCIS|ERZURUM|ESK[İI]SEHIR|ESK EH R|\bES TV\b|\bER TV\b|ETV KAYSERI|ETV MANISA|GAZIANTEP|\bICEL\b|K[İI]MARAS|KAHRAMANMARA|K MARAS|KAYSERI|KOCAELI|KON TV|KONYA|MALATYA|MERSIN|ORDU|ALTAS TV|SIVAS|TRABZON|TUNCELI|DERSIM|\bURFA\b|IZMIR TV|TON TV|KIBRIS|EDIRNE|DENIZLI|\bKAY TV\b|KENT T[UÜ]RK|KENT T RK|HUNAT|\bOBB\b|KANAL 12|KANAL 15|KANAL 23|KANAL 24|KANAL 26|KANAL 3\b|KANAL 32|KANAL 33|KANAL 34|KANAL 360|KANAL 42|KANAL 58|KANAL 68|KANAL FIRAT|KANAL URFA|KANAL V\b|\bKANAL Z\b|KANAL T\b|KANAL HAYAT|KANAL 68|KARADENIZ|GUNEYDOGU|GÜNEYDOĞU|\bEGE\b|MELTEM|CAY TV|TEK RUMEL|YENI KOCAELI|OLAY TV|\bGRT\b|SUN RTV|SUN TV|\bK[ÖO]Y TV\b|IZMIR|TIVI 6|TV 41|TV 42|TV 52|TV 264|KOZA TV|MC EU|MERCAN|KADIRGA|\bFANATIK\b|AS TV|ISVI|GURBET24|T\.A\.Y|TAY TV|\bTAY\b|\bTMB\b|AV TV|MAVI KARADENIZ|EGE ILE GAGA|GAZIANTEP GRT|VIYANA TV|LUYS|EDESSA|BIR TV|ANA[DK]OLU|B[İI]R TV|D[İI]YAR|ERTV|HRT|SIVAS|VIZYON 58|ADA TV|CAN TV|DEHA|SIFIR|EKIN T[UÜ]RK|AFROTURK|ARAS|ARKADAG|VATAN|D[ÖO]RU|AKSU TV|KARE TV|ON 4|ON 6|PAMUKKALE|UCANKUS|64 KARE|DENIZ POSTASI')
]

# Regex desenlerini derleme
COMPILED_RULES = [(cat, re.compile(pattern, re.IGNORECASE)) for cat, pattern in CATEGORY_RULES]

def categorize(name: str) -> str:
    s = normalize_for_category(name)
    for cat, pattern in COMPILED_RULES:
        if pattern.search(s):
            return cat
    return "TR Diğer"


# -- M3U Dosyası Oluşturma ------------------------------------------------

def escape_attr(value: Optional[str]) -> str:
    s = str(value or "")
    s = re.sub(r"[\r\n]+", " ", s)
    return s.replace('"', "'")


def to_stream_url(item: Dict[str, Any]) -> str:
    global proxy_index
    url = item.get("url", "")
    if not url:
        return ""

    if len(PROXY_LIST) > 0:
        current_proxy = PROXY_LIST[proxy_index]
        proxy_index = (proxy_index + 1) % len(PROXY_LIST)
        return f"{current_proxy}/?url={quote(url, safe='')}&master&transport=http&.m3u8"

    return url


def deduplicate_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    filtered = []
    for item in items:
        if not item or not item.get("url"):
            continue

        v_id = item.get("ids", {}).get("id") if isinstance(item.get("ids"), dict) else None
        key = f"{v_id}-{item['url']}" if v_id else item["url"]

        if key in seen:
            continue

        seen.add(key)
        filtered.append(item)
    return filtered


def to_m3u(items: List[Dict[str, Any]]) -> str:
    lines = ["#EXTM3U"]
    for it in items:
        vavoo_id = (
            it.get("ids", {}).get("id", "")
            if isinstance(it.get("ids"), dict)
            else ""
        )
        raw_name = it.get("name")
        clean_name = clean_channel_name(raw_name)
        if not clean_name:
            continue

        logo = it.get("logo", "")
        raw_group = it.get("group", "")

        # Grup kontrolü: "Turkey" veya boşsa kategorize et
        if not raw_group or raw_group.lower() == "turkey":
            group = categorize(clean_name)
        else:
            group = raw_group

        stream_url = to_stream_url(it)

        lines.append(
            f'#EXTINF:-1 tvg-id="{escape_attr(vavoo_id)}" '
            f'tvg-name="{escape_attr(clean_name)}" '
            f'tvg-logo="{escape_attr(logo)}" '
            f'group-title="{escape_attr(group)}",{clean_name}'
        )
        lines.append(stream_url)

    lines.append("")
    return "\n".join(lines)


def get_sort_key(item: Dict[str, Any]):
    name = clean_channel_name(item.get("name", "")).casefold()
    v_id = (
        item.get("ids", {}).get("id", "")
        if isinstance(item.get("ids"), dict)
        else ""
    )
    return (name, v_id)


def main():
    print(f"Veri çekiliyor: {CATALOG_URL} ...")
    print(f"Algılanan ve Kullanılacak Aktif Proxy Sayısı: {len(PROXY_LIST)}")

    raw_items = fetch_all()

    print(f"Toplam ham kanal sayısı: {len(raw_items)}")

    items = deduplicate_items(raw_items)
    if len(raw_items) != len(items):
        print(f"Mükerrer yayınlar temizlendi. Kalan kanal sayısı: {len(items)}")

    # İsme ve ID'ye göre sıralama
    items.sort(key=get_sort_key)

    m3u_content = to_m3u(items)

    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print(f"Başarıyla oluşturuldu: {M3U_FILE} ({len(items)} kanal)")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"Kritik Hata: {err}")
        exit(1)
