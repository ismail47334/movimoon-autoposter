import os, requests, random, re, time, asyncio, json, subprocess
from datetime import datetime, timedelta
from pathlib import Path

print("=== MoviMoon Bot - MASTER V9 FAST 10-TRY ===")

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
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=15).json()
            results = [m for m in r.get("results", []) if m.get("id")]
            for m in results:
                if 'media_type' not in m:
                    m['media_type'] = 'tv' if 'first_air_date' in m else 'movie'
            all_results.extend(results[:8])
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
    random.shuffle(filtered)
    seen = set()
    unique = []
    for m in filtered:
        if m['id'] not in seen:
            unique.append(m)
            seen.add(m['id'])
    print(f"Found {len(unique)} unique, returning 10")
    return unique[:10]  # user requested 10 tries

def get_youtube_trailer(movie):
    tmdb_id = movie['id']
    m_type = movie.get('media_type','movie')
    if m_type not in ['movie','tv']: m_type = 'movie'
    url = f"https://api.themoviedb.org/3/{m_type}/{tmdb_id}/videos?api_key={TMDB_API_KEY}&language=en-US"
    try:
        r = requests.get(url, timeout=10).json()
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

def download_via_ytdlp_fixed(youtube_url, output="trailer.mp4"):
    print(f"YT-DLP START {youtube_url}")
    Path(output).unlink(missing_ok=True)
    cookie_arg = ""
    if Path("cookies.txt").exists() and Path("cookies.txt").stat().st_size > 100:
        cookie_arg = "--cookies cookies.txt"
        print("Using cookies.txt")
    strategies = [
        f'yt-dlp {cookie_arg} -f "best[height<=720][ext=mp4]/best[height<=720]/best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --force-ipv4 --no-warnings -q --retries 1 --fragment-retries 1',
        f'yt-dlp {cookie_arg} --extractor-args "youtube:player_client=android" -f "best[height<=720]/best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --force-ipv4 --no-warnings -q --retries 1',
        f'yt-dlp {cookie_arg} -f "worstvideo[height>=360]+worstaudio/worst" -o "{output}" "{youtube_url}" --no-playlist --force-ipv4 --no-warnings -q --retries 1',
    ]
    for i, cmd in enumerate(strategies, 1):
        try:
            print(f"Trying strategy {i}...")
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            if Path(output).exists() and Path(output).stat().st_size > 30000:
                size_mb = Path(output).stat().st_size/1024/1024
                print(f"YT-DLP SUCCESS {i} - {size_mb:.2f} MB")
                return output
            else:
                print(f"Strategy {i} failed")
            Path(output).unlink(missing_ok=True)
        except subprocess.TimeoutExpired:
            print(f"Strategy {i} TIMEOUT 60s")
            Path(output).unlink(missing_ok=True)
            continue
        except Exception as e:
            print(f"Strategy {i} err {e}")
            continue
    print("ALL YT-DLP STRATEGIES FAILED")
    return None

def download_trailer(youtube_url, output="trailer.mp4"):
    return download_via_ytdlp_fixed(youtube_url, output)

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

def generate_local_cinematic_bgm(output="bgm.mp3", category="cinematic", duration=65):
    try:
        if Path(output).exists():
            try: Path(output).unlink()
            except: pass
        print(f"Generating local {category} BGM...")
        if category == "suspense":
            cmd = f'ffmpeg -y -f lavfi -i "sine=frequency=40:beep_factor=8:sample_rate=48000:duration={duration},aecho=0.8:0.9:1000:0.3,lowpass=f=400,volume=0.18" -f lavfi -i "sine=frequency=80:beep_factor=12:duration={duration},aecho=0.8:0.88:800:0.25,lowpass=f=500,volume=0.12" -filter_complex "[0:a][1:a]amix=inputs=2:duration=longest,apulsator=hz=0.15,volume=0.25" -c:a libmp3lame -q:a 4 "{output}"'
        elif category == "epic_action":
            cmd = f'ffmpeg -y -f lavfi -i "sine=frequency=55:beep_factor=4:duration={duration},aecho=0.8:0.88:60:0.4,volume=0.20" -f lavfi -i "sine=frequency=110:beep_factor=6:duration={duration},aecho=0.8:0.9:120:0.3,volume=0.15" -filter_complex "[0:a][1:a]amix=inputs=2,lowpass=f=600,apulsator=hz=0.5,volume=0.30" -c:a libmp3lame -q:a 4 "{output}"'
        elif category == "emotional":
            cmd = f'ffmpeg -y -f lavfi -i "sine=frequency=196.00:duration={duration},aecho=0.8:0.88:500:0.35,volume=0.18" -f lavfi -i "sine=frequency=261.63:duration={duration},aecho=0.8:0.9:600:0.3,volume=0.12" -filter_complex "[0:a][1:a]amix=inputs=2,lowpass=f=1200,volume=0.22" -c:a libmp3lame -q:a 4 "{output}"'
        elif category == "happy":
            cmd = f'ffmpeg -y -f lavfi -i "sine=frequency=196:duration={duration},apulsator=hz=0.8,volume=0.15" -f lavfi -i "sine=frequency=246:duration={duration},apulsator=hz=1.0,volume=0.10" -filter_complex "[0:a][1:a]amix=inputs=2,highpass=f=200,lowpass=f=2000,volume=0.20" -c:a libmp3lame -q:a 4 "{output}"'
        else:
            cmd = f'ffmpeg -y -f lavfi -i "sine=frequency=55:duration={duration},aecho=0.8:0.88:60:0.4,lowpass=f=800,volume=0.20" -f lavfi -i "sine=frequency=110:duration={duration},aecho=0.8:0.9:120:0.3,lowpass=f=1000,volume=0.12" -filter_complex "[0:a][1:a]amix=inputs=2,volume=0.25" -c:a libmp3lame -q:a 4 "{output}"'
        subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if Path(output).exists() and Path(output).stat().st_size > 1000:
            print(f"Local BGM OK {Path(output).stat().st_size/1024:.1f} KB")
            return output
        cmd2 = f'ffmpeg -y -f lavfi -i "sine=frequency=80:duration={duration}" -c:a libmp3lame -q:a 9 -filter:a "volume=0.15,lowpass=f=500" "{output}"'
        subprocess.run(cmd2, shell=True, capture_output=True, timeout=20)
        if Path(output).exists():
            return output
    except Exception as e:
        print(f"Local BGM error {e}")
    return None

def ensure_bgm(output="bgm.mp3", movie=None):
    try:
        genre_ids = movie.get("genre_ids", []) if movie else []
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
        print(f"BGM Category: {category}")
        return generate_local_cinematic_bgm(output, category, duration=65)
    except Exception as e:
        print(f"BGM err {e}")
        return generate_local_cinematic_bgm(output, "cinematic", duration=65)

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
        voice = f"বন্ধুরা কেমন আছেন সবাই আজকে কথা বলবো {year} সালের আলোচিত সিনেমা নিয়ে। এই সিনেমার গল্পটা এতটাই টানটান উত্তেজনায় ভরা যে একবার দেখা শুরু করলে শেষ না করে উঠতে পারবেন না। প্রধান চরিত্রের অসাধারণ অভিনয় দুর্দান্ত পরিচালনা এবং আবহ সঙ্গীত আপনাকে এক মুহূর্তের জন্যও বিরক্ত হতে দেবে না। বিশেষ করে গল্পের শেষের চমকটা আপনার মাথা ঘুরিয়ে দেবে। যারা রোমাঞ্চ এবং অ্যাকশন পছন্দ করেন তাদের জন্য এটা অবশ্যই দেখার মতো একটি সিনেমা। পুরো সিনেমাটির বিস্তারিত রিভিউ পেয়ে যাবেন আমাদের ওয়েবসাইট মুভিমুন ডট অনলাইন এ। এখনই ভিজিট করুন। বন্ধুরা এই সিনেমাটি কিন্তু আপনাদের মন ছুঁয়ে যাবে। এই গল্পের প্রতিটা মুহূর্ত আপনাকে আটকে রাখবে শেষ পর্যন্ত।"
        caption = f"🎬 Movie - {title} ({year})\n🎭 Genre - {genre_str}\n⭐ Rating - {rating}/10\n🔗 Link: {link}\n#MoviMoon"
        return voice, caption

    prompt = f"""You are the Senior Bengali Voiceover Director & Lead Scriptwriter for MoviMoon.
Your core objective is to write an engaging, dramatic, and precise 60-second Bengali video narration script based on the provided movie details.

### CRITICAL REQUIREMENTS (WORD COUNT):
- STRICT WORD COUNT: EXACTLY between 165 and 180 Bengali words. 
- UNDER NO CIRCUMSTANCES should the word count be less than 165 words (Short scripts cause audio timing failure).
- Do a strict self-count before generating the final JSON response.

### INPUT DATA:
- Movie Title: {title}
- Release Year: {year}
- Rating: {rating}/10
- Genre: {genre_str}
- Overview/Plot: {overview}
- Movie Link: {link}

### SCRIPT STRUCTURE & TIMING BREAKDOWN:
1. HOOK (0-10s) -> [28 to 30 words]: High energy opening to grab attention instantly.
2. STORY PLOT (10-30s) -> [55 to 60 words]: Brief, intriguing core synopsis without spoilers.
3. ACTING & VISUALS (30-50s) -> [50 to 55 words]: Critique of performance, direction, atmosphere, or climax setup.
4. CALL TO ACTION / OUTRO (50-60s) -> [25 to 30 words]: Wrap up with rating mention and direct audience to watch on MoviMoon via the link.

### LANGUAGE RULES:
1. 100% Pure Bengali text using proper Bengali punctuation (। , ! ?).
2. NO English words, letters, or numbers in the "voiceover" text (Transliterate English titles/numbers into Bengali, e.g., 8.5 -> ৮.৫ or সাড়ে আট).
3. Transliterate the movie title cleanly into Bengali for "bangla_title".
4. Tone: Energetic, dramatic, and professional cinema narrator voice.

### REQUIRED OUTPUT FORMAT:
Return ONLY a valid, raw JSON object. Do NOT include markdown code blocks, explanations, or extra text.

{{
  "voiceover": "১৬৫ থেকে ১৮০ শব্দের পূর্ণাঙ্গ বাংলা ভয়েসওভার টেক্সট...",
  "bangla_title": "বাংলায় মুভির নাম",
  "caption": "আকর্ষণীয় সোশ্যাল মিডিয়া ক্যাপশন উইথ হ্যাশট্যাগ",
  "word_count": 172
}}"""

    models = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"]
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            data = {"contents":[{"parts":[{"text":prompt}]}], "generationConfig":{"temperature":0.9, "maxOutputTokens": 2500}}
            res = requests.post(url, json=data, timeout=30)
            if res.status_code == 200:
                js = res.json()
                try:
                    text = js["candidates"][0]["content"]["parts"][0]["text"]
                except:
                    continue
                clean_text = text.replace("```json","").replace("```","").strip()
                m = re.search(r'\{.*\}', clean_text, re.DOTALL)
                if m:
                    j = json.loads(m.group())
                    voice = j.get("voiceover","").strip()
                    caption = j.get("caption","").strip()
                    wc = len(voice.split())
                    print(f"Gemini {model} OK - {wc} words")
                    # If 140-160, still accept but log warning - better than failing all
                    if wc < 140:
                        print(f"Accepting short {wc} words (will be ~40-50s, usable)")
                    if link not in caption:
                        caption += f"\n\nLink: {link}"
                    return voice, caption
            print(f"Gemini {model} fail {res.status_code}")
        except Exception as e:
            print(f"Gemini {model} err {e}")
            continue
    return None, None

async def generate_tts_voice(text, output_path="voice.mp3"):
    print(f"TTS: {len(text.split())} words RATE +28%")
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
        if not has_bgm:
            bgm_path = generate_local_cinematic_bgm("bgm.mp3", "cinematic", 65)
            has_bgm = Path(bgm_path).exists()
        
        # FIX: -loop only for image (poster), not for mp3. Use -stream_loop for bgm or no loop + aloop filter
        if poster_path and Path(poster_path).exists():
            cmd = (
                f'ffmpeg -y -loop 1 -t 65 -i "{poster_path}" '
                f'-i "{trailer_path}" -i "{voice_path}" -stream_loop -1 -i "{bgm_path}" '
                f'-filter_complex "'
                f'[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=18:steps=2,setsar=1,trim=duration=65[bg];'
                f'[1:v]scale=1080:800:force_original_aspect_ratio=increase,crop=1080:800[fg];'
                f'[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1:format=auto,scale=1080:1920:flags=lanczos[base];'
                f'[1:a]volume=0.10[trailera];'
                f'[2:a]volume=1.0,loudnorm=I=-14:TP=-1.5:LRA=11[voicea];'
                f'[3:a]volume=0.22[bgma];'
                f'[trailera][bgma][voicea]amix=inputs=3:duration=longest:dropout_transition=0:weights=0.1 0.22 1.0,volume=1.3,loudnorm=I=-14:TP=-1.5:LRA=11[a]" '
                f'-map "[base]" -map "[a]" '
                f'-c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -r 30 '
                f'-c:a aac -b:a 192k -t 65 "{output}"'
            )
        else:
            cmd = (
                f'ffmpeg -y -i "{trailer_path}" -i "{voice_path}" -stream_loop -1 -i "{bgm_path}" '
                f'-filter_complex "'
                f'[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=18:steps=2[bg];'
                f'[0:v]scale=1080:800:force_original_aspect_ratio=increase,crop=1080:800[fg];'
                f'[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,scale=1080:1920:flags=lanczos[base];'
                f'[0:a]volume=0.10[trailera];'
                f'[1:a]volume=1.0,loudnorm=I=-14:TP=-1.5:LRA=11[voicea];'
                f'[2:a]volume=0.22[bgma];'
                f'[trailera][bgma][voicea]amix=inputs=3:duration=longest:dropout_transition=0:weights=0.1 0.22 1.0,volume=1.3[a]" '
                f'-map "[base]" -map "[a]" '
                f'-c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p -r 30 '
                f'-c:a aac -b:a 192k -t 65 "{output}"'
            )
        print("FFmpeg 9:16 HD + BGM...")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=180)
        if Path(output).exists() and Path(output).stat().st_size > 50000:
            print(f"Final OK {Path(output).stat().st_size/1024/1024:.2f} MB {get_video_duration(output):.1f}s")
            return output
        print(f"FFmpeg err {result.stderr[-500:]}")
        return None
    except Exception as e:
        print(f"9:16 Error {e}")
        return None

def upload_video_to_facebook(page_id, token, video_path, caption, label):
    try:
        url = f"https://graph.facebook.com/v19.0/{page_id}/videos"
        with open(video_path, 'rb') as f:
            files = {'source': f}
            data = {'description': caption, 'access_token': token}
            r = requests.post(url, files=files, data=data, timeout=300)
            print(f"{label}: {r.status_code}")
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
    print("=== MAIN START V8 FAST ===")
    history = load_history()
    items = get_trending_mixed()
    print(f"Found {len(items)} items, max 5")
    for idx, movie in enumerate(items):
        try:
            tmdb_id = str(movie.get('id'))
            title_raw = movie.get('title') or movie.get('name') or "Unknown"
            print(f"\n>>> [{idx+1}/{len(items)}] {title_raw} ({tmdb_id})")
            if is_already_posted(tmdb_id, history, days=30):
                print(f"SKIPPED")
                continue
            yt_url, yt_key = get_youtube_trailer(movie)
            if not yt_url:
                print(f"No trailer")
                continue
            title = title_raw
            year = (movie.get("release_date") or movie.get("first_air_date") or "2025")[:4]
            rating = round(movie.get("vote_average",0), 1)
            overview = movie.get("overview","")[:600]
            link, m_type = build_movimoon_link(movie)
            voice_text, caption = call_gemini_video_script(title, year, m_type, rating, overview, link, movie=movie)
            if not voice_text:
                print(f"Gemini failed")
                continue
            trailer_file = download_trailer(yt_url, "trailer.mp4")
            if not trailer_file:
                print(f"Trailer download failed, skip")
                continue
            poster_file = download_movie_poster(movie, "poster.jpg")
            bgm_file = ensure_bgm("bgm.mp3", movie=movie)
            trailer_60s = trim_trailer_to_60s(trailer_file, "trailer_60s.mp4")
            asyncio.run(generate_tts_voice(voice_text, "voice.mp3"))
            print(f"Voice {get_video_duration('voice.mp3'):.1f}s Trailer {get_video_duration(trailer_60s):.1f}s BGM {get_video_duration(bgm_file):.1f}s")
            final_video = create_9_16_hd_video(trailer_60s, poster_file, "voice.mp3", "final.mp4", bgm_path=bgm_file)
            if not final_video:
                continue
            success = False
            if FB_PAGE_ID and FB_PAGE_TOKEN:
                resp = upload_video_to_facebook(FB_PAGE_ID, FB_PAGE_TOKEN, final_video, caption, "PAGE")
                if resp and resp.status_code == 200:
                    success = True
                    print("PAGE SUCCESS")
            if FB_GROUP_ID and FB_PAGE_TOKEN and success:
                time.sleep(3)
                resp2 = upload_video_to_facebook(FB_GROUP_ID, FB_PAGE_TOKEN, final_video, caption, "GROUP")
                print(f"GROUP {resp2.status_code if resp2 else 'fail'}")
            if success:
                history[tmdb_id] = datetime.now().isoformat()
                save_history(history)
            for f in ["trailer.mp4","trailer_60s.mp4","voice.mp3","final.mp4","poster.jpg","bgm.mp3"]:
                if os.path.exists(f):
                    try: os.remove(f)
                    except: pass
            print("Done 1 video exit")
            break
        except Exception as e:
            print(f"MAIN ERROR: {e}")
            import traceback; traceback.print_exc()
            continue
    print("=== MAIN END ===")

if __name__ == "__main__":
    main()
