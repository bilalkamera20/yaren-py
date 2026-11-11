import os
import re
import uuid
import time
import json
import urllib.parse
import requests

# ============================================================
#  SABİTLER VE PROXY TANIMLARI
# ============================================================
UA             = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
CLIENT_VERSION = '3.1.4'
CATALOG_URL    = 'https://vavoo.to/mediahubmx-catalog.json'
OUTPUT_FILE    = 'nernur.txt'

# Gelişmiş Yedekli Worker Proxy Havuzu
FALLBACK_PROXIES = [
    "https://1.vavturktv.workers.dev",
    "https://2.vavturktv.workers.dev",
    "https://3.vavturktv.workers.dev",
    "https://4.vavturktv.workers.dev",
    "https://5.vavturktv.workers.dev",
    "https://6.vavturktv.workers.dev",
    "https://7.vavturktv.workers.dev",
    "https://8.vavturktv.workers.dev",
    "https://9.vavturktv.workers.dev",
    "https://10.vavturktv.workers.dev",
    "https://11.vavturktv.workers.dev",
    "https://12.vavturktv.workers.dev",
    "https://13.vavturktv.workers.dev",
    "https://14.vavturktv.workers.dev",
    "https://15.vavturktv.workers.dev",
    "https://16.vavturktv.workers.dev",
    "https://17.vavturktv.workers.dev",
    "https://18.vavturktv.workers.dev",
    "https://19.vavturktv.workers.dev",
    "https://20.vavturktv.workers.dev",
    "https://21.vavturktv.workers.dev",
    "https://22.vavturktv.workers.dev",
    "https://23.vavturktv.workers.dev",
    "https://24.vavturktv.workers.dev",
    "https://25.vavturktv.workers.dev",
    "https://nur.bilalkamera20.workers.dev",
    "https://halil.bilalkamera20.workers.dev",
    "https://adam.bilalkamera20.workers.dev",
    "https://bilal.bilalkamera20.workers.dev",
    "https://balkica.bilalkamera20.workers.dev",
    "https://hmeb.bilalkamera20.workers.dev",
    "https://nernur.bilalkamera20.workers.dev",
    "https://vav20.bilalkamera20.workers.dev",
    "https://vavoo-iptv-proxy.bilalkamera20.workers.dev",
    "https://yaren.bilalkamera20.workers.dev",
    "https://denem.bilalkamera20.workers.dev",
    "https://20.bilalkamera20.workers.dev",
    "https://yw.bilalkamera20.workers.dev",
    "https://fb.bilalkamera20.workers.dev",
    "https://ner.bilalkamera20.workers.dev"
]

PING_URLS = [
    'https://www.vypn.net/api/app/ping',
    'https://www.vavoo.tv/api/app/ping',
    'https://cache.vypn.net/api/app/ping',
]

DEFAULT_GROUPS = [
    'Turkey'
]

# Ortam değişkeninden (ENV) PROXY_BASE değerini al ve ayrıştır
def parse_env_proxies():
    env_proxy = os.getenv('PROXY_BASE')
    if not env_proxy:
        return []
    raw_list = re.split(r'[,;\r\n]+', env_proxy)
    proxies = []
    for item in raw_list:
        trimmed = item.strip()
        if trimmed:
            proxies.append(trimmed.rstrip('/'))
    return proxies

env_proxies = parse_env_proxies()
worker_proxies = env_proxies if env_proxies else FALLBACK_PROXIES

# ============================================================
#  HTTP POST
# ============================================================
def http_post(url, payload, extra_headers=None):
    if extra_headers is None:
        extra_headers = {}
    
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'User-Agent': UA,
        'Accept': '*/*',
    }
    headers.update(extra_headers)

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=20, verify=False)
        return {
            'ok': response.status_code < 400,
            'body': response.text,
            'code': response.status_code,
            'err': None
        }
    except Exception as e:
        return {'ok': False, 'body': None, 'code': 0, 'err': str(e)}

# ============================================================
#  TOKEN (İmza Alımı)
# ============================================================
def get_signature():
    uid = uuid.uuid4().hex
    ts = round(time.time() * 1000)
    payload = {
        'reason': 'app-focus', 'locale': 'de', 'theme': 'dark',
        'metadata': {
            'device':  {'type': 'desktop', 'uniqueId': uid},
            'os':      {'name': 'win32', 'version': 'Windows 10 Pro',
                          'abis': ['x64'], 'host': 'PC'},
            'app':     {'platform': 'electron'},
            'version': {'package': 'net.vypn.app', 'binary': '3.1.0', 'js': '3.1.0'},
        },
        'appFocusTime': 0, 'playerActive': False, 'playDuration': 0,
        'devMode': False, 'hasAddon': True, 'castConnected': False,
        'package': 'net.vypn.app', 'version': '3.1.0', 'process': 'app',
        'firstAppStart': ts, 'lastAppStart': ts, 'ipLocation': None,
        'adblockEnabled': True,
        'proxy': {'supported': ['ss'], 'engine': 'Mu', 'enabled': False, 'autoServer': True},
        'iap':   {'supported': False},
    }
    
    for u in PING_URLS:
        r = http_post(u, payload)
        if r['ok']:
            try:
                d = json.loads(r['body'])
                sig = d.get('sig') or d.get('addonSig') or d.get('signature') or d.get('token')
                if sig:
                    return sig
            except json.JSONDecodeError:
                continue
    return None

# ============================================================
#  TEMİZLEME VE KATEGORİZASYON FONKSİYONLARI
# ============================================================
def clean_channel_name(name):
    if not name:
        return "Bilinmeyen Kanal"

    s = str(name)
    s = re.sub(r'^\s*(?:4K\s*)?TR\s*:\s*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s*\.[bcs]\b', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s+(?:4K|UHD|FHD|HD\+|HD|SD|HEVC|RAW|H265|H\.265|FEED)(?=\s|$)', '', s, flags=re.IGNORECASE)
    s = re.sub(r'S\s*[\x00-\x1F\x7F-\xFF\?\s]*NEMA', 'SINEMA', s, flags=re.IGNORECASE)
    s = re.sub(r'DREAM\s*T\s*R\s*K', 'DREAM TURK', s, flags=re.IGNORECASE)
    s = re.sub(r'MINICA', 'MINIKA', s, flags=re.IGNORECASE)
    s = re.sub(r'\s+', ' ', s)

    return s.strip()

def normalize_for_category(name):
    s = clean_channel_name(name)

    char_map = {
        'Ç': 'C', 'ç': 'c',
        'Ğ': 'G', 'ğ': 'g',
        'İ': 'I', 'I': 'I', 'ı': 'i',
        'Ö': 'O', 'ö': 'o',
        'Ş': 'S', 'ş': 's',
        'Ü': 'U', 'ü': 'u'
    }
    for k, v in char_map.items():
        s = s.replace(k, v)

    search_patterns = [
        r'\bT RK\b', r'\bT RKIYEM\b', r'\bBENG\b', r'\bBENGT\b', r'\bAK T\b', 
        r'\bS\s*NEMA\b', r'\bM N KA\b', r'\bOCUK\b', r'\bM Z K\b', r'\bS ZC\b', 
        r'\bSZC\b', r'\bLKE\b', r'\bYE IL AM\b', r'\bYE IL[ ]?CAM\b', r'\bT[ÜU]RK\b'
    ]
    replace_values = [
        'TURK', 'TURKIYEM', 'BENGU', 'BENGUT', 'AKIT', 'SINEMA', 'MINIKA', 
        'COCUK', 'MUZIK', 'SOZCU', 'SOZCU', 'ULKE', 'YESILCAM', 'YESILCAM', 'TURK'
    ]

    for pat, rep in zip(search_patterns, replace_values):
        s = re.sub(pat, rep, s, flags=re.IGNORECASE)

    return s

def categorize_channel(name):
    s = normalize_for_category(name)

    if re.search(r'KARADENIZ\s*BRT|TRT\s*MUZIK', s, re.IGNORECASE):
        return 'TR Diğer'

    rules = {
        'TR Spor': r'BEIN SPO[RT]{0,3}S?|\bBEIN 1\b|S[- ]?SPORTS?|\bS SPORT\b|SPOR SMART|EUROSPORT|\bNBA\b|TJK TV|TIVIBU ?SPOR|TIVIBUSPOR|TRT SPOR|TABII SPOR|EXXEN SPO[RT]?|\bHT SPOR\b|EKOL SPOR|SPORTS TV|IDMAN TV|GALATASARAY TV|\bFB TV\b|\bGS TV\b|SARAN SPORT|SMART SPOR|\bSPOR\b|\bSPORT\b',
        'TR Radyo': r'\b(RADIO|RADYO)\b|\b(FM|MBAT FM|EFKAR FM|FMTV|F ?M)\b(?!\s*TV)|POWERTURK|POWER FM|SHOW RADYO|ALEM (?:FM|RADYO)|BABA RADYO|KRAL POP RADYO|PAL STATION|X NOSTALJI|RADIO ROCK|STANBUL FM',
        'TR Çocuk': r'CARTOON|BOOMERANG|DISNEY|NICK(?:ELODEON|TOONS|JR|JUNIOR|\b)|BABY ?TV|BABYTV|MINIKA|MINICA|POKEMON|ANIMATION|ANIMASYON|TRT ?COCUK|COCUK HD|\bCOCUK\b|ANKA|BEN ?10|ANGRY BIRDS|CAILLOU|PEPPA|PEPE|HEIDI|SIRINLER|TOM & JERRY|SUNGER|SUNGER\s*BOB|SPIDERMAN|BARBIE|PIJAMA|PIRIL|RAFADAN|KELOGLAN|KUKULI|KUKILI|KOSTEBEK|CHICKY|BOOBA|WAKFU|GABBY|TAYO|NILOYA|PISI|LEYLEK|MASAL|CANIM KARDESIM|ADIBESA|MOMO|ALVIN|VIKINGLER|TRANSFORMERS|TROL AVCILARI|SMART\s*COCUK|COCUK\s*SMART|ILAHI COCUK|CILGIN ORMAN|KRAL SAKIR|SERCE KUS|ITFAYECI SAM|MUFFETIS|MAYMUNLAR|ELIF VE|ELIFIN|MIMOCAN|HAPSUU|RUYA TRENI|MASA KOCAAYI|PAK PIRPIR|LIMON ZEYTIN|GONCA TV|NASREDDIN|SEKER HOCA|SEVIMLI DOSTLAR|PAW PETROL|OSCAR COLLERDE|SL NILOYA|CBEEBIES|DUCK TV|JIM ?JAM|ENGLISH CLUB TV|EBA TV|TAVSAN|PATRON BEBEK|DIYARI|BAHA\b|SEF ROKKA|BULMACA KULESI|AKILLI TAVSAN|AKLILI|DA VINC KIDS|DA VINCI KIDS|DINAMIK ANIMASYON|BEST ANIMASYON|YILDIZ KIZ|KONUSAN TOM|JURASSIC WORLD|MONTAG|64\s*KARE',
        'TR Belgesel': r'DISCOVERY|NATIONAL GEOGRAPHIC|NAT ?GEO|\bHISTORY\b|ANIMAL PLANET|DA VINCI(?! KIDS)|VIASAT|BBC EARTH|LOVE NATURE|TRT BELGESEL|EPIC DRAMA|TARIH TV|TARIM TV|TGRT BELGESEL|INVESTIGATION|DMAX|DOCUBOX|DOCU SCREEN|SCIENCE|\bIZ TV\b|YABAN|OUTDOOR|CHASSE|ANIMAUX|AGRO TV|CIFTCI TV|REDBULL TV|\bTLC\b',
        'TR Yaşam': r'24 KITCHEN|GURME|BEIN GURME|LIFESTYLE|\bLIFE TV\b|FASHION|WM TV|EGE ILE GAGA|24 RAW|\bTVEM\b|\bTV EM\b|AUTOMOTO|LINE TV|BILGILENDIRME|WOMAN|TELEGRAM',
        'TR Haber': r'\b24\s*TV\b|\bTV\s*24\b|\b24\s*HABER\b|^24$|\bHABER\b|\bNEWS\b|BLOOMBERG|\bCNN\b|EKOTURK|\bEKO ?TURK\b|\bEKOL\b|A ?PARA|APARA|PARANIN|HALK TV|TELE ?1|SOZCU|\bSZC\b|BENGU|BENGUTURK|TRT WORLD|TRT HABER|\bDHA\b|LIDER HABER|FLASH|FLASH HABER|MEDYA HABER|GLOBAL HABER|TRABZON HABER|BEIN SPORTS HABER|TURKHABER|HABERTURK|\bARTI TV\b|\bAKIT\b|TVNET|TV NET|MELTEM|A HABER|ULKE|A NEWS|KRT|ULUSAL',
        'TR Film': r'DREAM|DINAMIK\s*TURK|SINEMA|CINEMA|SINEMAX|SINEVIZYON|\bMOVIES?\b|MOVIEMAX|MOVIESMART|BEIN MOVIES|BEIN BOX|BOX OFFICE|\bFX\b|FX HD|YESILCAM|GLOBAL BOX|PROTURK|FIX CINEMA|KINGBOX|ARENA BOX|SHOWMAX|SHOW MAX|REAL BOX|SMART BOX|BEST (?:AKSIYON|BILIMKURGU|DRAM|HABABAM|IMBD|KOMEDI|KORKU|LOCA|NETFLIX|SALON|SAVAS|TURK|WESTERN|YESILCAM)|MAX|\bLOCA\b|\bSALON\b|\bVIZYON\b|AKSIYON|KOMEDI|\bKORKU\b|\bDRAM\b|WESTERN|BILIM ?KURGU|\bSAVAS\b|\bIMBD\b|\bIMDB\b|\bFILM\b|FILMBOX|HORROR|OSCAR|KEMAL SUNAL|\b007\b|\bCINE ?1\b|SIFIR TV|SON C BOOM|\bYERLI\b|SPIDERMAN(?! TV)|ARENA BOX|MOVIE SMART|\bMTURK TV\b',
        'TR Ulusal': r'\bTRT\b|\bTRT 1\b|\bTRT ?2\b|TRT2|\bTRT 3\b|TRT AVAZ|TRT TURK|TRT KURDI|TRT 4K|TRT EBA|\bKANAL D\b|\bATV\b|ATV AVRUPA|ATV EUROPA|STAR TV|\bSTAR\b|STAR HD|SHOW TV|SHOW TURK|\bSHOW\b|\bFOX\b|NOW ?TV|\bNOW\b|TV ?8|TV8[.,]5|BEYAZ TV|BEYAZ HD|\bBEYAZ\b|\b360\b|\bA2\b|TV ?100|TV ?4|TEVE ?2|TEVE2|CNN TURK|\bBRT ?[0-9]|\bBRTV\b|EURO ?D|EURO ?STAR|\bNTV\b|EXXEN TV|TIVITURK|TABII|OLAY TURK|KANAL AVRUPA|\bKANAL 7\b|KANAL 7 (?:AVRUPA|EUROPA)|EURO D|EURO STAR|SHOW TV EUROPA|TGRT EU|DUGUN TV|\bTBMM\b|\bTV 1\b|TVO TV|BEIN IZ',
        'TR Dizi': r'SERIES|\bDIZI\b|BEIN SERIES|DIZISMART',
        'TR Müzik': r'POWER TURK|POWER ?TV|POWERTURK|POWER (?:DANCE|LOVE|HD)|\bPOWER\b|KRAL POP|KRAL ?TV|\bKRAL\b|NR ?1|NUMBER ?1|NUMBER ONE|DAMAR|ARABESK|AKUSTIK|AHMET KAYA|IBRAHIM ERKAL|IBRAHIM TATLISES|\bTATLISES\b|ZERRIN OZER|SEZEN AKSU|TARKAN|SELDA BAGCAN|CENGIZ KURTOGLU|MAHSUN KIRMIZIGUL|MUSLUM GURSES|YILDIZ TILBE|FERDI TAYFUR|DURSUN AL|MTV LIVE|VINTAGE MUSIC|RETRO TURK|TURKCE POP|TURKCE KLASIK|SLOW KARADENIZ|\bSLOW\b|\bZARA\b|\bSONER ARICA\b|MUZIK|\bFM TV\b|\bFMTV\b|REDBOX',
        'TR Dini': r'DIYANET|MEHTAP|HILAL|KUDUS|SEMERKAND|LALEGUL|MERCAN TV|VUSLAT|KARDELEN|DIYAR TV|\bDOST TV\b|\bYOL TV\b|HAYAT|HAYIRLI|HZ MERYEM|HZ OMER|HZ YUSUF|MAM EBU|ASHABI KEHF|HASAN VE HUSEYIN|SAT ?7 TURK|TRT DIYANET|\bTV ?5\b|\bTV5\b|REHBER|ILAHI|ILKE TV|MESAJ TV|SURELER|TURKCE MEAL|DURSUN AL ERZINCANLI|YUNUS EMRE|CEM TV|BARBAROS TV|ASLAN TV|TYT TURK|SATRANC|FASIL',
        'TR Yerel': r'TVDEN|TV DEN|ADANA|ADIYAMAN|AFYON|AKSARAY|ALANYA|ANAKKALE|\bANKARA\b|ANKA TV|ANKARA TURKIYEM|SANLIURFA|ANTALYA|\bBURSA\b|ELAZIG|ERCIS|ERZURUM|ESKISEHIR|\bES TV\b|\bER TV\b|ETV KAYSERI|ETV MANISA|GAZIANTEP|\bICEL\b|KAHRAMANMARAS|KAYSERI|KOCAELI|KON TV|KONYA|MALATYA|MERSIN|ORDU|ALTAS TV|SIVAS|TRABZON|TUNCELI|DERSIM|\bURFA\b|IZMIR TV|TON TV|KIBRIS|EDIRNE|DENIZLI|\bKAY TV\b|KENT TURK|HUNAT|\bOBB\b|KANAL 12|KANAL 15|KANAL 23|KANAL 24|KANAL 26|KANAL 3\b|KANAL 32|KANAL 33|KANAL 34|KANAL 360|KANAL 42|KANAL 58|KANAL 68|KANAL FIRAT|KANAL URFA|KANAL V\b|\bKANAL Z\b|KANAL T\b|KANAL HAYAT|GUNEYDOGU|\bEGE\b|TEK RUMELI|YENI KOCAELI|OLAY TV|\bGRT\b|SUN RTV|SUN TV|\bKOY TV\b|IZMIR|TIVI 6|TV 41|TV 42|TV 52|TV 264|KOZA TV|MC EU|MERCAN|KADIRGA|\bFANATIK\b|AS TV|ISVI|GURBET24|T\.A\.Y|TAY TV|\bTAY\b|\bTMB\b|AV TV|MAVI KARADENIZ|EGE ILE GAGA|GAZIANTEP GRT|VIYANA TV|LUYS|EDESSA|BIR TV|ANADOLU|DIYAR|ERTV|HRT|VIZYON 58|ADA TV|CAN TV|DEHA|SIFIR|EKIN TURK|AFROTURK|ARAS|ARKADAG|VATAN|DORU|AKSU TV|KARE TV|ON 4|ON 6|PAMUKKALE|UCANKUS|DENIZ POSTASI'
    }

    for cat, pattern in rules.items():
        if re.search(pattern, s, flags=re.IGNORECASE):
            return cat

    return 'TR Diğer'

# ============================================================
#  KATALOG ÇEKME
# ============================================================
def fetch_catalog_group(group, signature):
    channels = []
    cursor = 0
    for _ in range(15):
        payload = {
            'language': 'tr', 'region': 'TR', 'catalogId': 'iptv', 'id': 'iptv',
            'adult': False, 'search': '', 'sort': 'name',
            'filter': {'group': group},
            'cursor': cursor, 'clientVersion': CLIENT_VERSION,
        }
        r = http_post(CATALOG_URL, payload, {'mediahubmx-signature': signature})
        if not r['ok']:
            break
        
        try:
            data = json.loads(r['body'])
        except json.JSONDecodeError:
            break
            
        if not isinstance(data, dict):
            break
            
        items = data.get('items', [])
        if not items:
            break

        for itm in items:
            raw_name = itm.get('name', '')
            name = clean_channel_name(raw_name)
            if not name:
                name = 'Isimsiz Kanal'

            resolved_group = categorize_channel(raw_name)

            chid = ''
            ids = itm.get('ids')
            if isinstance(ids, dict):
                chid = ids.get('id', '')
            if not chid:
                chid = itm.get('id', '')

            url = itm.get('url') or itm.get('play', '')
            if not url and chid:
                url = f"https://vavoo.to/vavoo-iptv/play/{chid}"
            elif url and '/play/' in url and '/vavoo-iptv/' not in url:
                url = re.sub(r'^https?://[^/]+/play/', 'https://vavoo.to/vavoo-iptv/play/', url)
            
            if not url:
                continue

            logo = ''
            images = itm.get('images')
            if isinstance(images, dict):
                logo = images.get('logo') or images.get('poster', '')
            if not logo:
                logo = itm.get('logo') or itm.get('poster', '')

            tvg = ''
            if isinstance(ids, dict):
                tvg = ids.get('tvg', '')

            channels.append({
                'name':   name, 
                'url':    url, 
                'group':  resolved_group,
                'logo':   logo, 
                'tvg_id': tvg,
            })
            
        cursor = data.get('nextCursor', 0)
        if not cursor:
            break
            
    return channels

# ============================================================
#  M3U ÜRETİMİ
# ============================================================
def build_m3u(channels, proxies):
    out = ["#EXTM3U"]
    out.append(f"#EXT-X-USER-AGENT:{UA}")
    out.append("#EXT-X-REFERER:https://vavoo.to/")
    out.append("#EXT-X-ORIGIN:https://vavoo.to")

    proxy_count = len(proxies)
    proxy_index = 0

    for ch in channels:
        logo = f' tvg-logo="{ch["logo"]}"' if ch['logo'] else ''
        tvg  = f' tvg-id="{ch["tvg_id"]}"' if ch['tvg_id'] else ''
        
        out.append(f'#EXTINF:-1{tvg} tvg-name="{ch["name"]}"{logo} group-title="{ch["group"]}",{ch["name"]}')
        
        active_proxy = proxies[proxy_index % proxy_count]
        proxy_index += 1

        out.append(f"{active_proxy.rstrip('/')}/?url={urllib.parse.quote(ch['url'])}&master&transport=http&.m3u8")
        
    return "\n".join(out) + "\n"

# ============================================================
#  ANA İŞLEM
# ============================================================
if __name__ == '__main__':
    # Uyarı mesajlarını bastırmak için (requests SSL uyarısı)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    sig = get_signature()
    if not sig:
        print("Hata: İmza alınamadı!")
        exit(1)

    all_channels = []
    for g in DEFAULT_GROUPS:
        all_channels.extend(fetch_catalog_group(g, sig))

    if not all_channels:
        print("Hata: Kanal bulunamadı!")
        exit(1)

    m3u_content = build_m3u(all_channels, worker_proxies)

    # Çıktıyı nernur.txt dosyasına yaz
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)

    print(f"Başarılı! {len(all_channels)} kanal işlendi ve '{OUTPUT_FILE}' dosyasına kaydedildi.")
