import os, requests, random, re, time, asyncio, json, subprocess
from datetime import datetime, timedelta
from pathlib import Path

print("=== MoviMoon Bot - FINAL PRO 9:16 HD + GENRE BGM + PURE BENGALI ===")

try:
    import edge_tts
    print("edge_tts OK")
except Exception as e:
    print(f"edge_tts fail {e}")
    import sys; sys.exit(1)

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
FB_GROUP_ID = os.getenv("FB_GROUP_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

VOICE = "bn-IN-BashkarNeural"
RATE = "+28%"
PITCH = "+2Hz"
VOLUME = "+35%"
HISTORY_FILE = "posted_history.json"

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text).strip('-')
    return text[:60]

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_history(history):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"History Save Error: {e}")

def is_already_posted(tmdb_id, history, days=30):
    tmdb_id = str(tmdb_id)
    if tmdb_id not in history:
        return False
    try:
        last_date = datetime.fromisoformat(history[tmdb_id])
        if datetime.now() - last_date < timedelta(days=days):
            return True
    except:
        return False
    return False

def get_trending_mixed():
    current_year = datetime.now().year
    min_year = current_year - 2
    min_date = f"{min_year}-01-01"
    print(f"Filtering: Only {min_year}+")
    all_results = []
    urls = [
        f"https://api.themoviedb.org/3/trending/movie/day?api_key={TMDB_API_KEY}&language=en-US",
        f"https://api.themoviedb.org/3/trending/tv/day?api_key={TMDB_API_KEY}&language=en-US",
        f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&primary_release_date.gte={min_date}&sort_by=popularity.desc&vote_count.gte=20&page=1",
        f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_original_language=hi&primary_release_date.gte={min_date}&sort_by=popularity.desc&vote_count.gte=10&page=1",
        f"https://api.themoviedb.org/3/discover/tv?api_key={TMDB_API_KEY}&first_air_date.gte={min_date}&sort_by=popularity.desc&vote_count.gte=20&page=1",
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=15).json()
            results = [m for m in r.get("results", []) if m.get("id")]
            for m in results:
                if 'media_type' not in m:
                    m['media_type'] = 'tv' if 'first_air_date' in m else 'movie'
            all_results.extend(results[:10])
        except Exception as e:
            print(f"TMDB Error: {e}")
            continue
    filtered = []
    for m in all_results:
        try:
            date_str = m.get("release_date") or m.get("first_air_date") or ""
            if not date_str: continue
            year = int(date_str[:4])
            if year >= min_year:
                filtered.append(m)
        except:
            continue
    print(f"Fetched: {len(all_results)}, After {min_year}+: {len(filtered)}")
    random.shuffle(filtered)
    seen = set()
    unique = []
    for m in filtered:
        if m['id'] not in seen:
            unique.append(m)
            seen.add(m['id'])
    return unique[:15]

def get_youtube_trailer(movie):
    tmdb_id = movie['id']
    m_type = movie.get('media_type','movie')
    if m_type not in ['movie','tv']: m_type = 'movie'
    url = f"https://api.themoviedb.org/3/{m_type}/{tmdb_id}/videos?api_key={TMDB_API_KEY}&language=en-US"
    try:
        r = requests.get(url, timeout=15).json()
        for v in r.get('results', []):
            if v.get('site')=='YouTube' and v.get('type')=='Trailer':
                return f"https://www.youtube.com/watch?v={v['key']}", v['key']
        for v in r.get('results', []):
            if v.get('site')=='YouTube':
                return f"https://www.youtube.com/watch?v={v['key']}", v['key']
    except Exception as e:
        print(f"Trailer API Error: {e}")
    return None, None

def get_video_duration(video_path):
    try:
        cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{video_path}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return float(result.stdout.strip())
    except:
        return 0

def get_cookie_arg():
    if Path("cookies.txt").exists() and Path("cookies.txt").stat().st_size > 100:
        return '--cookies cookies.txt'
    return ''

def download_via_ytdlp_fixed(youtube_url, output="trailer.mp4"):
    print(f"\n=== YT-DLP HD for {youtube_url} ===")
    Path(output).unlink(missing_ok=True)
    cookie_arg = get_cookie_arg()
    deno_bin = f"{os.path.expanduser('~')}/.deno/bin/deno"
    js_arg = f"--js-runtimes deno:{deno_bin}" if Path(deno_bin).exists() else "--js-runtimes deno"
    strategies = [
        f'yt-dlp {cookie_arg} {js_arg} --extractor-args "youtube:player_client=android,web" -f "bestvideo[height>=720][height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080][ext=mp4]+bestaudio/best[height>=720]" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --force-ipv4',
        f'yt-dlp {cookie_arg} --extractor-args "youtube:player_client=android" -f "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --force-ipv4',
        f'yt-dlp {cookie_arg} -f "best[height>=720][ext=mp4]/best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --force-ipv4',
    ]
    for i, cmd in enumerate(strategies, 1):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=180)
            if Path(output).exists() and Path(output).stat().st_size > 50000:
                print(f"YT-DLP SUCCESS {i} - {Path(output).stat().st_size/1024/1024:.2f} MB")
                return output
            Path(output).unlink(missing_ok=True)
        except Exception as e:
            print(f"Strategy {i} err {e}")
            continue
    return None

def download_via_cobalt_fixed(youtube_url, output="trailer.mp4"):
    Path(output).unlink(missing_ok=True)
    instances = ["https://api.cobalt.tools/api/json", "https://co.wuk.sh/api/json"]
    for api in instances:
        try:
            payload = {"url": youtube_url, "vCodec": "h264", "vQuality": "1080", "isAudioOnly": False}
            r = requests.post(api, json=payload, headers={"Accept":"application/json","Content-Type":"application/json"}, timeout=20)
            if r.status_code == 200:
                dl_url = r.json().get("url")
                if dl_url:
                    with requests.get(dl_url, stream=True, timeout=90) as dl:
                        with open(output,'wb') as f:
                            for chunk in dl.iter_content(1024*1024):
                                if chunk: f.write(chunk)
                    if Path(output).exists() and Path(output).stat().st_size > 50000:
                        return output
        except Exception as e:
            print(f"Cobalt {api} err {e}")
            continue
    return None

def download_trailer(youtube_url, output="trailer.mp4"):
    res = download_via_ytdlp_fixed(youtube_url, output)
    if res: return res
    res = download_via_cobalt_fixed(youtube_url, output)
    if res: return res
    return None

def download_movie_poster(movie, output="poster.jpg"):
    try:
        poster_path = movie.get("poster_path")
        if not poster_path:
            return None
        url = f"https://image.tmdb.org/t/p/w780{poster_path}"
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            with open(output, 'wb') as f:
                f.write(r.content)
            if Path(output).exists() and Path(output).stat().st_size > 1000:
                return output
    except Exception as e:
        print(f"Poster err {e}")
    return None

def get_genre_names(genre_ids):
    genre_map = {
        28: "অ্যাকশন", 12: "অ্যাডভেঞ্চার", 16: "অ্যানিমেশন", 35: "কমেডি",
        80: "ক্রাইম", 99: "ডকুমেন্টারি", 18: "ড্রামা", 10751: "ফ্যামিলি",
        14: "ফ্যান্টাসি", 36: "ইতিহাস", 27: "হরর", 10402: "মিউজিক",
        9648: "মিস্ট্রি", 10749: "রোমান্স", 878: "সায়েন্স ফিকশন",
        10770: "টিভি মুভি", 53: "থ্রিলার", 10752: "ওয়ার", 37: "ওয়েস্টার্ন"
    }
    if not genre_ids:
        return "ড্রামা, থ্রিলার"
    names = [genre_map.get(g, "") for g in genre_ids[:3] if g in genre_map]
    return ", ".join(names) if names else "ড্রামা, থ্রিলার"

def ensure_bgm(output="bgm.mp3", movie=None):
    try:
        if Path(output).exists() and movie:
            try: Path(output).unlink()
            except: pass
        genre_ids = movie.get("genre_ids", []) if movie else []
        overview = (movie.get("overview","") + " " + movie.get("title","")).lower() if movie else ""
        category = "cinematic"
        if any(g in genre_ids for g in [27, 53, 9648, 80]):
            category = "suspense"
        elif any(g in genre_ids for g in [28, 12, 10752, 37]):
            category = "epic_action"
        elif any(g in genre_ids for g in [35, 16, 10751]):
            category = "happy"
        elif any(g in genre_ids for g in [10749, 18, 36]):
            category = "emotional"
        elif any(g in genre_ids for g in [878, 14]):
            category = "cinematic_futuristic"
        else:
            if any(k in overview for k in ["horror", "thrill", "murder", "crime", "mystery", "scary", "ghost"]):
                category = "suspense"
            elif any(k in overview for k in ["action", "fight", "war", "battle", "mission"]):
                category = "epic_action"
            elif any(k in overview for k in ["love", "romance", "romantic"]):
                category = "emotional"
            elif any(k in overview for k in ["comedy", "funny", "laugh"]):
                category = "happy"
            elif any(k in overview for k in ["space", "future", "alien", "sci-fi"]):
                category = "cinematic_futuristic"
        print(f"BGM Category: {category} for genre_ids {genre_ids}")
        BGM_LIBRARY = {
            "epic_action": [
                "https://cdn.pixabay.com/download/audio/2022/01/13/audio_3633571fb7.mp3?filename=epic-cinematic-trailer-112956.mp3",
                "https://cdn.pixabay.com/download/audio/2021/08/04/audio_0625c1539c.mp3?filename=epic-110042.mp3",
                "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a83be5.mp3?filename=cinematic-time-lapse-115672.mp3",
            ],
            "suspense": [
                "https://cdn.pixabay.com/download/audio/2022/10/30/audio_fbd6d5ddac.mp3?filename=dark-cinematic-ambient-129451.mp3",
                "https://cdn.pixabay.com/download/audio/2021/09/14/audio_619339fbc7.mp3?filename=dark-ambient-106515.mp3",
                "https://cdn.pixabay.com/download/audio/2022/03/24/audio_7c8c1a0e13.mp3?filename=suspense-ambient-117551.mp3",
            ],
            "emotional": [
                "https://cdn.pixabay.com/download/audio/2022/06/07/audio_b9bd4170e8.mp3?filename=cinematic-documentary-112669.mp3",
                "https://cdn.pixabay.com/download/audio/2021/10/25/audio_0556d62dd9.mp3?filename=sad-piano-112199.mp3",
                "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07c.mp3?filename=romantic-piano-111914.mp3",
            ],
            "happy": [
                "https://cdn.pixabay.com/download/audio/2022/06/15/audio_a83a4a6b1c.mp3?filename=happy-upbeat-113864.mp3",
                "https://cdn.pixabay.com/download/audio/2021/08/09/audio_5fc7f9aa97.mp3?filename=happy-background-111196.mp3",
            ],
            "cinematic_futuristic": [
                "https://cdn.pixabay.com/download/audio/2022/03/24/audio_5b7cb1bc5c.mp3?filename=futuristic-ambient-117615.mp3",
                "https://cdn.pixabay.com/download/audio/2022/10/14/audio_13ef4c7c54.mp3?filename=space-atmosphere-128814.mp3",
            ],
            "cinematic": [
                "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a83be5.mp3?filename=cinematic-time-lapse-115672.mp3",
                "https://cdn.pixabay.com/download/audio/2021/11/17/audio_872d32a0d3.mp3?filename=epic-cinematic-ambience-112030.mp3",
            ]
        }
        urls = BGM_LIBRARY.get(category, BGM_LIBRARY["cinematic"])
        random.shuffle(urls)
        for url in urls:
            try:
                print(f"Downloading {category} BGM...")
                r = requests.get(url, timeout=40, stream=True, headers={"User-Agent":"Mozilla/5.0"})
                if r.status_code == 200:
                    with open(output, 'wb') as f:
                        for chunk in r.iter_content(32768):
                            if chunk: f.write(chunk)
                    if Path(output).exists() and Path(output).stat().st_size > 30000:
                        print(f"BGM {category} OK {Path(output).stat().st_size/1024:.1f}KB")
                        return output
                    Path(output).unlink(missing_ok=True)
            except Exception as e:
                print(f"BGM err {e}")
                continue
        if category != "cinematic":
            return ensure_bgm(output, movie=None)
        return None
    except Exception as e:
        print(f"BGM ensure err {e}")
        return None

def trim_trailer_to_60s(input_path, output_path="trailer_60s.mp4"):
    try:
        if Path(output_path).exists(): Path(output_path).unlink()
        cmd = f'ffmpeg -y -i "{input_path}" -t 60 -c:v libx264 -preset fast -crf 23 -c:a aac "{output_path}"'
        subprocess.run(cmd, shell=True, capture_output=True, timeout=90)
        if Path(output_path).exists(): return output_path
        return input_path
    except Exception as e:
        print(f"Trim err {e}")
        return input_path

def call_gemini_video_script(title, year, m_type, rating, overview, link, movie=None):
    genre_str = get_genre_names(movie.get("genre_ids", []) if movie else [])
    if not GEMINI_API_KEY:
        voice = f"বন্ধুরা কেমন আছেন সবাই আজকে কথা বলবো {year} সালের আলোচিত সিনেমা {title} নিয়ে। বন্ধুরা এই সিনেমার গল্পটা এতটাই টানটান উত্তেজনায় ভরা যে একবার দেখা শুরু করলে শেষ না করে উঠতে পারবেন না। প্রধান চরিত্রের অসাধারণ অভিনয় দুর্দান্ত পরিচালনা এবং আবহ সঙ্গীত আপনাকে এক মুহূর্তের জন্যও বিরক্ত হতে দেবে না। বিশেষ করে গল্পের শেষের চমকটা আপনার মাথা ঘুরিয়ে দেবে। যারা রোমাঞ্চ এবং অ্যাকশন পছন্দ করেন তাদের জন্য এটা অবশ্যই দেখার মতো একটি সিনেমা। পুরো সিনেমাটির বিস্তারিত রিভিউ পেয়ে যাবেন আমাদের ওয়েবসাইট মুভিমুন ডট অনলাইন এ। এখনই ভিজিট করুন। বন্ধুরা এই সিনেমাটি কিন্তু আপনাদের মন ছুঁয়ে যাবে।"
        caption = f"🎬 Movie - {title} ({year})\n\n🎭 Genre - {genre_str}\n⭐ IMDb Rating - {rating}/10\n📖 Story - {overview[:250]}...\n\n🔗 ফুল মুভি লিংক: {link}\n\n👉 পুরো রিভিউ এবং এইচডি ডাউনলোড পেতে ভিজিট করুন movimoon.online\n\n#MoviMoon #MovieReview #TrendingMovie #BengaliReview"
        return voice, caption

    prompt = f"""
You are MoviMoon Bengali Critic. Write 100% PURE BENGALI voiceover, NO ENGLISH. Even movie title MUST be in Bengali phonetic.

DATA:
Original Title: {title}
Year: {year}
Rating: {rating}
Genre: {genre_str}
Plot: {overview}
Link: {link}

VOICEOVER RULES:
1. 100% Bengali only. NO English. Title {title} must be transliterated to Bengali, e.g. Avatar -> অ্যাভাটার, John Wick -> জন উইক.
2. Forbidden in voiceover: Movie, Story, Action, VFX, BGM, CGI, IMDb, HD, OTT, AI, Rating, Genre - write all in Bengali.
3. Length: 140 to 160 words EXACT. Count.
4. Structure: Hook, Story, Acting, Why Watch, CTA with movimoon.online.
5. Tone natural spoken Bengali for TTS bn-IN-BashkarNeural.

OUTPUT JSON ONLY:
{{
"voiceover": "140-160 words pure Bengali, no English, title in Bengali phonetic...",
"bangla_title": "Title in Bengali phonetic",
"caption": "🎬 Movie - {title} ({year})\\n\\n🎭 Genre - {genre_str}\\n⭐ IMDb Rating - {rating}/10\\n📖 Story - [Bengali 30 words]\\n\\n[hook line Bengali]\\n\\n🔗 ফুল মুভি লিংক: {link}\\n\\n👉 পুরো রিভিউ এবং এইচডি ডাউনলোড পেতে ভিজিট করুন movimoon.online\\n\\n#MoviMoon #MovieReview #TrendingNow #MustWatch #BengaliReview #ViralReels"
}}
"""
    models = [
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.8-flash-lite",
        "gemini-flash-latest",
        "gemini-2.5-flash"
    ]
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            data = {"contents":[{"parts":[{"text":prompt}]}], "generationConfig":{"temperature":0.85, "maxOutputTokens": 2000}}
            res = requests.post(url, json=data, timeout=60)
            if res.status_code == 200:
                text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                m = re.search(r'\{.*\}', text, re.DOTALL)
                if m:
                    j = json.loads(m.group())
                    voice = j.get("voiceover","").strip()
                    caption = j.get("caption","").strip()
                    if voice and caption:
                        wc = len(voice.split())
                        print(f"Gemini {model} OK - {wc} words - {j.get('bangla_title','')}")
                        if link not in caption:
                            caption += f"\n\n🔗 ফুল মুভি লিংক: {link}"
                        return voice, caption
            print(f"Gemini {model} fail {res.status_code} {res.text[:400]}")
        except Exception as e:
            print(f"Gemini {model} err {e}")
            continue
    return None, None

async def generate_tts_voice(text, output_path="voice.mp3"):
    # Pure Bengali cleaning - ensure no English words for clear pronunciation
    # Replace common English terms with Bengali
    repl = {
        "VFX": "ভিজুয়াল এফেক্ট", "AI": "কৃত্রিম বুদ্ধিমত্তা", "BGM": "আবহ সঙ্গীত",
        "CGI": "কম্পিউটার গ্রাফিক্স", "IMDb": "রেটিং", "IMDB": "রেটিং",
        "OTT": "ওটিটি", "HD": "এইচডি", "4K": "ফোর কে"
    }
    for en, bn in repl.items():
        text = text.replace(en, bn)
    # Remove any remaining isolated English words (keep Bengali only)
    # We keep it simple - Gemini already gives pure Bengali, this is extra safety
    print(f"TTS: {len(text.split())} words - RATE +28% - Pure Bengali check")
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH, volume=VOLUME)
    await communicate.save(output_path)
    try:
        loud_path = output_path.replace(".mp3", "_loud.mp3")
        os.system(f'ffmpeg -y -i "{output_path}" -filter:a loudnorm=I=-14:TP=-1.5:LRA=11 "{loud_path}"')
        if os.path.exists(loud_path):
            os.replace(loud_path, output_path)
    except:
        pass
    return output_path

def create_9_16_hd_video(trailer_path, poster_path, voice_path, output="final.mp4", bgm_path=None):
    try:
        if Path(output).exists(): Path(output).unlink()
        has_bgm = bgm_path and Path(bgm_path).exists()
        print(f"BGM: {'YES' if has_bgm else 'NO'}")
        if poster_path and Path(poster_path).exists():
            if has_bgm:
                cmd = (
                    f'ffmpeg -y -loop 1 -t 65 -i "{poster_path}" '
                    f'-i "{trailer_path}" -i "{voice_path}" -loop 1 -t 65 -i "{bgm_path}" '
                    f'-filter_complex "'
                    f'[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=18:steps=2,setsar=1,trim=duration=65[bg];'
                    f'[1:v]scale=1080:800:force_original_aspect_ratio=increase,crop=1080:800[fg];'
                    f'[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1:format=auto,scale=1080:1920:flags=lanczos[base];'
                    f'[1:a]volume=0.10[trailera];'
                    f'[2:a]volume=1.0,loudnorm=I=-14:TP=-1.5:LRA=11[voicea];'
                    f'[3:a]volume=0.18,aloop=loop=-1:size=2e+09[bgma];'
                    f'[trailera][bgma][voicea]amix=inputs=3:duration=shortest:dropout_transition=0:weights=0.1 0.18 1.0,volume=1.3,loudnorm=I=-14:TP=-1.5:LRA=11[a]" '
                    f'-map "[base]" -map "[a]" '
                    f'-c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -r 30 '
                    f'-c:a aac -b:a 192k -shortest -t 65 "{output}"'
                )
            else:
                cmd = (
                    f'ffmpeg -y -loop 1 -t 60 -i "{poster_path}" '
                    f'-i "{trailer_path}" -i "{voice_path}" '
                    f'-filter_complex "'
                    f'[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=18:steps=2,setsar=1,trim=duration=60[bg];'
                    f'[1:v]scale=1080:800:force_original_aspect_ratio=increase,crop=1080:800[fg];'
                    f'[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1:format=auto,scale=1080:1920:flags=lanczos[base];'
                    f'[1:a]volume=0.12[trailera];'
                    f'[2:a]volume=1.0,loudnorm=I=-14:TP=-1.5:LRA=11[voicea];'
                    f'[trailera][voicea]amix=inputs=2:duration=shortest:dropout_transition=0,volume=1.2[a]" '
                    f'-map "[base]" -map "[a]" '
                    f'-c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p -r 30 '
                    f'-c:a aac -b:a 192k -shortest -t 65 "{output}"'
                )
        else:
            if has_bgm:
                cmd = (
                    f'ffmpeg -y -i "{trailer_path}" -i "{voice_path}" -loop 1 -t 65 -i "{bgm_path}" '
                    f'-filter_complex "'
                    f'[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=18:steps=2[bg];'
                    f'[0:v]scale=1080:800:force_original_aspect_ratio=increase,crop=1080:800[fg];'
                    f'[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,scale=1080:1920:flags=lanczos[base];'
                    f'[0:a]volume=0.10[trailera];'
                    f'[1:a]volume=1.0,loudnorm=I=-14:TP=-1.5:LRA=11[voicea];'
                    f'[2:a]volume=0.18,aloop=loop=-1:size=2e+09[bgma];'
                    f'[trailera][bgma][voicea]amix=inputs=3:duration=shortest:dropout_transition=0:weights=0.1 0.18 1.0,volume=1.3[a]" '
                    f'-map "[base]" -map "[a]" '
                    f'-c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p -r 30 '
                    f'-c:a aac -b:a 192k -shortest -t 65 "{output}"'
                )
            else:
                cmd = (
                    f'ffmpeg -y -i "{trailer_path}" -i "{voice_path}" '
                    f'-filter_complex "'
                    f'[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=18:steps=2[bg];'
                    f'[0:v]scale=1080:800:force_original_aspect_ratio=increase,crop=1080:800[fg];'
                    f'[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,scale=1080:1920:flags=lanczos[base];'
                    f'[0:a]volume=0.12[trailera];'
                    f'[1:a]volume=1.0,loudnorm=I=-14:TP=-1.5:LRA=11[voicea];'
                    f'[trailera][voicea]amix=inputs=2:duration=shortest:dropout_transition=0,volume=1.2[a]" '
                    f'-map "[base]" -map "[a]" '
                    f'-c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p -r 30 '
                    f'-c:a aac -b:a 192k -shortest -t 65 "{output}"'
                )
        print(f"FFmpeg 9:16 HD PRO +28%...")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=180)
        if Path(output).exists() and Path(output).stat().st_size > 50000:
            probe_cmd = f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=WxH "{output}"'
            probe_res = subprocess.run(probe_cmd, shell=True, capture_output=True, text=True)
            print(f"Final 9:16 HD: {probe_res.stdout.strip()} - {Path(output).stat().st_size/1024/1024:.2f} MB")
            return output
        print(f"FFmpeg err {result.stderr[-800:]}")
        return None
    except Exception as e:
        print(f"9:16 Error {e}")
        import traceback; traceback.print_exc()
        return None

def upload_video_to_facebook(page_id, token, video_path, caption, label):
    try:
        url = f"https://graph.facebook.com/v19.0/{page_id}/videos"
        with open(video_path, 'rb') as f:
            files = {'source': f}
            data = {'description': caption, 'access_token': token}
            r = requests.post(url, files=files, data=data, timeout=300)
            print(f"{label}: {r.status_code} {r.text[:500]}")
            return r
    except Exception as e:
        print(f"FB Error: {e}")
        return None

def build_movimoon_link(movie):
    tmdb_id = movie.get("id")
    title = movie.get("title") or movie.get("name") or "untitled"
    slug = slugify(title)
    media_type = movie.get("media_type")
    if media_type == "tv":
        return f"https://movimoon.online/tv/{tmdb_id}-{slug}", media_type
    else:
        return f"https://movimoon.online/movie/{tmdb_id}-{slug}", "movie"

def main():
    print("=== MAIN START - 9:16 HD + GENRE BGM + PURE BENGALI +28% ===")
    history = load_history()
    items = get_trending_mixed()
    print(f"Found {len(items)} items")
    if not items:
        return
    for movie in items:
        try:
            tmdb_id = str(movie.get('id'))
            title_raw = movie.get('title') or movie.get('name') or "Unknown"
            print(f"\n>>> Processing: {title_raw} ({tmdb_id})")
            if is_already_posted(tmdb_id, history, days=30):
                print(f"SKIPPED: {title_raw}")
                continue
            yt_url, yt_key = get_youtube_trailer(movie)
            if not yt_url:
                print(f"No trailer for {title_raw}")
                continue
            title = title_raw
            year = (movie.get("release_date") or movie.get("first_air_date") or "2025")[:4]
            rating = round(movie.get("vote_average",0), 1)
            overview = movie.get("overview","")[:600]
            link, m_type = build_movimoon_link(movie)
            voice_text, caption = call_gemini_video_script(title, year, m_type, rating, overview, link, movie=movie)
            if not voice_text or not caption:
                print(f"Gemini failed for {title_raw}")
                continue
            trailer_file = download_trailer(yt_url, "trailer.mp4")
            if not trailer_file:
                continue
            poster_file = download_movie_poster(movie, "poster.jpg")
            bgm_file = ensure_bgm("bgm.mp3", movie=movie)
            trailer_60s = trim_trailer_to_60s(trailer_file, "trailer_60s.mp4")
            asyncio.run(generate_tts_voice(voice_text, "voice.mp3"))
            final_video = create_9_16_hd_video(trailer_60s, poster_file, "voice.mp3", "final.mp4", bgm_path=bgm_file)
            if not final_video or not os.path.exists(final_video):
                print("Merge failed")
                continue
            success = False
            if FB_PAGE_ID and FB_PAGE_TOKEN:
                resp = upload_video_to_facebook(FB_PAGE_ID, FB_PAGE_TOKEN, final_video, caption, "PAGE")
                if resp and resp.status_code == 200:
                    success = True
                    print("PAGE SUCCESS")
            if FB_GROUP_ID and FB_PAGE_TOKEN and success:
                try:
                    time.sleep(3)
                    resp2 = upload_video_to_facebook(FB_GROUP_ID, FB_PAGE_TOKEN, final_video, caption, "GROUP")
                    if resp2 and resp2.status_code == 200:
                        print("GROUP SUCCESS")
                except Exception as ge:
                    print(f"GROUP err {ge}")
            if success:
                history[tmdb_id] = datetime.now().isoformat()
                save_history(history)
            for f in ["trailer.mp4","trailer_60s.mp4","voice.mp3","final.mp4","poster.jpg","bgm.mp3"]:
                if os.path.exists(f):
                    try: os.remove(f)
                    except: pass
            print("Done 1 video, exiting.")
            break
        except Exception as e:
            print(f"MAIN ERROR: {e}")
            import traceback; traceback.print_exc()
            continue
    print("=== MAIN END ===")

if __name__ == "__main__":
    main()
