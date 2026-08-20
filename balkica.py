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
        "language": "de",
        "region": "DE",
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


# -- Kanal İsmi Temizleme ve Kategorilendirme -----------------------------

def sanitize_name(name: Optional[str]) -> str:
    s = str(name or "")
    s = re.sub(r"^\s*(?:[A-Z0-9-]+\s+)*TR:\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*\.(?:b|c|s)\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[\r\n]+", " ", s)
    return s.strip()


def normalize_for_category(name: Optional[str]) -> str:
    clean = sanitize_name(name)
    clean = re.sub(
        r"\s+(?:UHD|FHD|HD\+|HD|SD|HEVC|RAW|H265|H\.265|FEED)(?=\s|$)",
        " ",
        clean,
        flags=re.IGNORECASE,
    )
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


CATEGORY_RULES = [
    {
        "name": "TR SPOR",
        "re": re.compile(
            r"\b(BEIN SPO[RT]{0,3}S?|BEIN 1|S[- ]?SPORTS?|S SPORT|SPOR SMART|EUROSPORT|NBA|TJK TV|TIVIBU ?SPOR|TIVIBUSPOR|TRT SPOR|TABII SPOR|EXXEN SPO[RT]?|HT SPOR|EKOL SPOR|SPORTS TV|IDMAN TV|GALATASARAY TV|FB TV|GS TV|SARAN SPORT|SMART SPOR|SPOR|SPORT)\b",
            re.IGNORECASE,
        ),
    },
    {
        "name": "TR ÇOCUK",
        "re": re.compile(
            r"\b(CARTOON|BOOMERANG|DISNEY|NICK(?:ELODEON|TOONS|JR|JUNIOR)?|BABY ?TV|BABYTV|M[İI]?N ?KA|MINIKA|POKEMON|POKÉMON|ANIMATION|ANIMASYON|TRT ?[ÇC]?OCUK|[ÇC]OCUK|BEN ?10|ANGRY BIRDS|CAILLOU|PEPPA|PEPE|HEIDI|SIRINLER|TOM & JERRY|SPIDERMAN|BARBIE|PIJAMA|PIRIL|RAFADAN|KELOGLAN|KUKULI|KUKILI|KOSTEBEK|CHICKY|BOOBA|WAKFU|GABBY|TAYO|NILOYA|PISI|LEYLEK|MASAL|CANIM KARDESIM|ADIBESA|MOMO|ALVIN|VIKINGLER|TRANSFORMERS|TROL AVCILARI|SMART COCUK|ILAHI COCUK|CILGIN ORMAN|KRAL SAKIR|SERCE KUS|ITFAYECI SAM|MUFFETIS|MAYMUNLAR|ELIF VE|ELIFIN|MIMOCAN|HAPSUU|RUYA TRENI|MASA KOCAAYI|PAK PIRPIR|LIMON ZEYTIN|GONCA TV|NASREDDIN|SEKER HOCA|SEVIMLI DOSTLAR|PAW PETROL|OSCAR COLLERDE|CBEEBIES|DUCK TV|JIM ?JAM|ENGLISH CLUB TV|EBA TV|PATRON BEBEK|DA VINC KIDS|DA VINCI KIDS)\b",
            re.IGNORECASE,
        ),
    },
    {
        "name": "TR BELGESEL",
        "re": re.compile(
            r"\b(DISCOVERY|NATIONAL GEOGRAPHIC|NAT ?GEO|HISTORY|ANIMAL PLANET|DA VINCI|VIASAT|BBC EARTH|LOVE NATURE|TRT BELGESEL|EPIC DRAMA|TARIH TV|TARIM TV|TGRT BELGESEL|INVESTIGATION|DMAX|DOCUBOX|DOCU SCREEN|SCIENCE|IZ TV|YABAN|OUTDOOR|CHASSE|ANIMAUX|AGRO TV|CIFTCI TV|REDBULL TV|TLC)\b",
            re.IGNORECASE,
        ),
    },
    {
        "name": "TR SİNEMA",
        "re": re.compile(
            r"\b(SINEMA|S[İI]NEMA|CINEMA|SINEMAX|SINEVIZYON|MOVIES?|MOVIEMAX|MOVIESMART|BEIN MOVIES|BEIN BOX|BOX OFFICE|FX|FX HD|YESILCAM|YE[ŞS]ILCAM|GLOBAL BOX|PROTURK|FIX CINEMA|KINGBOX|ARENA BOX|SHOWMAX|SHOW MAX|REAL BOX|SMART BOX|FILMBOX|HORROR|OSCAR|KEMAL SUNAL|007|CINE ?1|AKSIYON|KORKU|DRAM|WESTERN|BILIM ?KURGU|SAVAS|IMBD|IMDB|FILM)\b",
            re.IGNORECASE,
        ),
    },
    {
        "name": "TR DİZİ",
        "re": re.compile(
            r"\b(SER[İI]ES|DIZI|BEIN SERIES|D[İI]Z[İI] ?SMART|DIZISMART)\b",
            re.IGNORECASE,
        ),
    },
    {
        "name": "TR HABER",
        "re": re.compile(
            r"\b(HABER|NEWS|BLOOMBERG|CNN|EKOTURK|EKO ?T[UÜ]RK|EKOL|A ?PARA|APARA|PARANIN|HALK TV|TELE ?1|SOZCU|SZC|BENGU ?T[UÜ]RK|BENGUTURK|TRT WORLD|DHA|LIDER HABER|FLASH HABER|MEDYA HABER|GLOBAL HABER|TRABZON HABER|BEIN SPORTS HABER|T[UÜ]RKHABER|HABERT[UÜ]RK|HABERT RK|ARTI TV)\b",
            re.IGNORECASE,
        ),
    },
    {
        "name": "TR MÜZİK",
        "re": re.compile(
            r"\b(POWER T[UÜ]RK|POWER ?TV|POWERTURK|POWER|KRAL POP|KRAL ?TV|KRAL|TRT M[UÜ]?Z[İI]?K|TRT MUZIK|NR ?1|NUMBER ?1|NUMBER ONE|DAMAR|ARABESK|AKUSTIK|AHMET KAYA|IBRAHIM ERKAL|IBRAHIM TATLISES|TATLISES|ZERRIN OZER|SEZEN AKSU|TARKAN|SELDA BAGCAN|CENGIZ KURTOGLU|MAHSUN KIRMIZIGUL|MUSLUM GURSES|YILDIZ TILBE|FERDI TAYFUR|MTV LIVE|VINTAGE MUSIC|RETRO TURK|MUZIK|FM TV|FMTV|REDBOX)\b",
            re.IGNORECASE,
        ),
    },
    {
        "name": "TR RADYO",
        "re": re.compile(
            r"\b(RADIO|RADYO|FM|MBAT FM|EFKAR FM|FMTV|POWERTURK|POWER FM|SHOW RADYO|ALEM FM|BABA RADYO|KRAL POP RADYO|PAL STATION|X NOSTALJI|RADIO ROCK|ISTANBUL FM)\b",
            re.IGNORECASE,
        ),
    },
    {
        "name": "TR DİNİ",
        "re": re.compile(
            r"\b(D[İI]YANET|AK[İI]?T|MEHTAP|H[İI]LAL|KUDUS|KUDÜS|SEMERKAND|LALEGUL|LÂLEGÜL|MERCAN TV|VUSLAT|KARDELEN|DIYAR TV|DOST TV|YOL TV|KANAL 7|TVNET|TRT DIYANET|TV5|REHBER|ILAHI|ILKE TV|MESAJ TV|SURELER|CEM TV)\b",
            re.IGNORECASE,
        ),
    },
    {
        "name": "TR YAŞAM",
        "re": re.compile(
            r"\b(24 KITCHEN|GURME|BEIN GURME|LIFESTYLE|LIFE TV|FASHION|WM TV|24 RAW|TVEM|AUTOMOTO|LINE TV|BILGILENDIRME|WOMAN)\b",
            re.IGNORECASE,
        ),
    },
    {
        "name": "TR ULUSAL",
        "re": re.compile(
            r"\b(TRT|TRT 1|TRT 2|TRT 3|TRT AVAZ|TRT T[UÜ]RK|TRT KURD[İI]?|TRT WORLD|TRT 4K|TRT EBA|KANAL D|ATV|STAR TV|STAR|SHOW TV|SHOW|NOW ?TV|NOW|TV8|TV8[.,]5|BEYAZ TV|BEYAZ|360|24 TV|A2|A HABER|A NEWS|A PARA|A SPOR|TV100|TV4|FLASH TV|TEVE2|CNN T[UÜ]RK|KRT|ULUSAL KANAL|DREAM TURK|NTV|EXXEN TV|TABII|ULKE TV)\b",
            re.IGNORECASE,
        ),
    },
    {
        "name": "TR YEREL",
        "re": re.compile(
            r"\b(ADANA|ADIYAMAN|AFYON|AKSARAY|ALANYA|ANKARA|ANTALYA|BURSA|ELAZIG|ERZURUM|ESKISEHIR|GAZIANTEP|KAHRAMANMARAS|KAYSERI|KOCAELI|KONYA|MALATYA|MERSIN|ORDU|SIVAS|TRABZON|URFA|IZMIR|KIBRIS|DENIZLI|KANAL 12|KANAL 15|KANAL 23|KANAL 24|KANAL 26|KANAL 3|KANAL 32|KANAL 33|KANAL 42|KANAL 58|KANAL 68|KANAL FIRAT|KANAL URFA|KANAL V|KARADENIZ|EGE|MELTEM|CAY TV|OLAY TV|TIVI 6|TV 41|TV 42|TV 52|TV 264)\b",
            re.IGNORECASE,
        ),
    },
]


def categorize(name: str) -> str:
    s = normalize_for_category(name)
    for rule in CATEGORY_RULES:
        if rule["re"].search(s):
            return rule["name"]
    return "TR GENEL"


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
        name = sanitize_name(it.get("name"))
        if not name:
            continue

        logo = it.get("logo", "")
        group = categorize(name)
        stream_url = to_stream_url(it)

        lines.append(
            f'#EXTINF:-1 tvg-id="{escape_attr(vavoo_id)}" '
            f'tvg-name="{escape_attr(name)}" '
            f'tvg-logo="{escape_attr(logo)}" '
            f'group-title="{escape_attr(group)}",{name}'
        )
        lines.append(stream_url)

    lines.append("")
    return "\n".join(lines)


def get_sort_key(item: Dict[str, Any]):
    name = sanitize_name(item.get("name", "")).casefold()
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
