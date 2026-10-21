import os, requests, random, re, time, asyncio, json, subprocess
from datetime import datetime, timedelta
from pathlib import Path

print("=== MoviMoon Bot - FINAL V29 HD 1080p | FB + YT SHORTS | SEO + PAGE ONLY SUCCESS ===")

try:
    import edge_tts
    print("edge_tts OK")
except Exception as e:
    print(f"edge_tts fail {e}")
    import sys; sys.exit(1)

try:
    from groq import Groq
    GROQ_AVAILABLE = True
    print("Groq SDK available")
except ImportError:
    GROQ_AVAILABLE = False
    print("Groq not installed")

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
FB_GROUP_ID = os.getenv("FB_GROUP_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# YouTube Shorts - V29 NEW
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "")

VOICE = "bn-IN-BashkarNeural"
RATE = "+30%"
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
    print(f"Filtering: {min_year}+ | Hollywood + Bollywood + South + Series")
    all_results = []
    urls = [
        f"https://api.themoviedb.org/3/trending/movie/day?api_key={TMDB_API_KEY}&language=en-US",
        f"https://api.themoviedb.org/3/trending/tv/day?api_key={TMDB_API_KEY}&language=en-US",
        f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&primary_release_date.gte={min_date}&sort_by=popularity.desc&vote_count.gte=30&page=1",
        f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_original_language=hi&primary_release_date.gte={min_date}&sort_by=popularity.desc&vote_count.gte=10&page=1",
        f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_original_language=te&primary_release_date.gte={min_date}&sort_by=popularity.desc&vote_count.gte=5&page=1",
        f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_original_language=ta&primary_release_date.gte={min_date}&sort_by=popularity.desc&vote_count.gte=5&page=1",
        f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_original_language=ml&primary_release_date.gte={min_date}&sort_by=popularity.desc&vote_count.gte=3&page=1",
        f"https://api.themoviedb.org/3/discover/tv?api_key={TMDB_API_KEY}&first_air_date.gte={min_date}&sort_by=popularity.desc&vote_count.gte=20&page=1&with_origin_country=IN",
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
    random.shuffle(filtered)
    seen = set()
    unique = []
    for m in filtered:
        if m['id'] not in seen:
            unique.append(m)
            seen.add(m['id'])
    print(f"Total fetched {len(all_results)}, after filter {len(filtered)}, unique {len(unique)}")
    return unique[:10]

def get_youtube_trailer(movie):
    tmdb_id = movie['id']
    m_type = movie.get('media_type','movie')
    if m_type not in ['movie','tv']: m_type = 'movie'
    url = f"https://api.themoviedb.org/3/{m_type}/{tmdb_id}/videos?api_key={TMDB_API_KEY}&language=en-US"
    try:
        r = requests.get(url, timeout=10).json()
        results = r.get('results', [])
        def is_valid_trailer(v):
            if v.get('site') != 'YouTube':
                return False
            v_type = v.get('type','').lower()
            name = v.get('name','').lower()
            block_keywords = ['muhurat', 'mahurat', 'muhurath', 'making', 'behind', 'bts', 'featurette', 'interview', 'clip', 'scene', 'song', 'lyrical', 'audio', 'first look', 'announcement', 'motion poster', 'poster', 'greeting', 'launch', 'event']
            for kw in block_keywords:
                if kw in name:
                    return False
            if v_type in ['trailer', 'teaser']:
                return True
            return False
        valid = [v for v in results if is_valid_trailer(v)]
        def sort_key(v):
            type_order = 0 if v.get('type')=='Trailer' else 1
            official = 0 if v.get('official') else 1
            return (type_order, official)
        valid_sorted = sorted(valid, key=sort_key)
        if valid_sorted:
            v = valid_sorted[0]
            print(f"Trailer selected: {v.get('name')} | Type: {v.get('type')} | Official: {v.get('official')}")
            return f"https://www.youtube.com/watch?v={v['key']}", v['key']
        for v in results:
            if v.get('site')=='YouTube' and v.get('type')=='Trailer':
                lname = v.get('name','').lower()
                if 'muhurat' not in lname and 'mahurat' not in lname and 'making' not in lname:
                    print(f"Fallback Trailer: {v.get('name')} | {v.get('type')}")
                    return f"https://www.youtube.com/watch?v={v['key']}", v['key']
        print(f"No valid Trailer found for {tmdb_id}, skipping muhurat/making videos")
        return None, None
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
    print(f"YT-DLP START HD 1080p {youtube_url}")
    Path(output).unlink(missing_ok=True)
    cookie_arg = ""
    if Path("cookies.txt").exists() and Path("cookies.txt").stat().st_size > 100:
        cookie_arg = "--cookies cookies.txt"
        print(f"Using cookies.txt ({Path('cookies.txt').stat().st_size} bytes)")
    else:
        print("No cookies.txt, trying without")
    # HD 1080p - Try highest quality first, fallback to lower
    strategies = [
        f'yt-dlp {cookie_arg} -f "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --no-warnings -q --retries 1 --fragment-retries 1',
        f'yt-dlp {cookie_arg} -f "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --no-warnings -q --retries 1 --fragment-retries 1',
        f'yt-dlp {cookie_arg} --extractor-args "youtube:player_client=android" -f "best[height<=1080]/best[height<=720]/best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --no-warnings -q --retries 1',
        f'yt-dlp {cookie_arg} -f "best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --no-warnings -q --retries 1',
    ]
    for i, cmd in enumerate(strategies, 1):
        try:
            print(f"Trying HD strategy {i}...")
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            if Path(output).exists() and Path(output).stat().st_size > 50000:
                size_mb = Path(output).stat().st_size/1024/1024
                # Check actual height
                try:
                    probe = subprocess.run(f'ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=noprint_wrappers=1:nokey=1 "{output}"', shell=True, capture_output=True, text=True, timeout=10)
                    h = probe.stdout.strip()
                    print(f"YT-DLP SUCCESS {i} - {size_mb:.2f} MB - Height: {h}p HD")
                except:
                    print(f"YT-DLP SUCCESS {i} - {size_mb:.2f} MB HD")
                return output
            else:
                print(f"Strategy {i} failed - stdout:{result.stdout[-200:]} stderr:{result.stderr[-200:]}")
            Path(output).unlink(missing_ok=True)
        except subprocess.TimeoutExpired:
            print(f"Strategy {i} TIMEOUT after 60s")
            Path(output).unlink(missing_ok=True)
            continue
        except Exception as e:
            print(f"Strategy {i} err {e}")
            continue
    print("ALL YT-DLP FAILED")
    return None


def download_trailer(youtube_url, output="trailer.mp4"):
    return download_via_ytdlp_fixed(youtube_url, output)


def download_movie_poster(movie, output="poster.jpg"):
    try:
        poster_path = movie.get("poster_path")
        if not poster_path:
            return None
        url = f"https://image.tmdb.org/t/p/w1280{poster_path}"
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            with open(output, 'wb') as f:
                f.write(r.content)
            if Path(output).exists() and Path(output).stat().st_size > 1000:
                return output
    except Exception as e:
        print(f"Poster err {e}")
    return None

def get_genre_names(genre_ids, english=False):
    genre_map_en = {
        28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
        80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
        14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
        9648: "Mystery", 10749: "Romance", 878: "Sci-Fi",
        10770: "TV Movie", 53: "Thriller", 10752: "War", 37: "Western",
        10759: "Action", 10765: "Sci-Fi", 10762: "Kids", 10763: "News",
        10764: "Reality", 10767: "Talk"
    }
    if not genre_ids:
        return "Drama, Thriller"
    names = [genre_map_en.get(g, "") for g in genre_ids[:3] if g in genre_map_en]
    return ", ".join(names) if names else "Drama, Thriller"

def generate_local_cinematic_bgm(output="bgm.mp3", category="cinematic", duration=60):
    try:
        if Path(output).exists():
            Path(output).unlink(missing_ok=True)
        duration = int(duration)
        print(f"Generating {category} BGM {duration}s LOUDER...")
        if category == "suspense":
            cmd = f'ffmpeg -y -f lavfi -i "sine=frequency=40:beep_factor=8:sample_rate=48000:duration={duration},aecho=0.8:0.9:1000:0.3,lowpass=f=400,volume=0.35" -f lavfi -i "sine=frequency=80:beep_factor=12:duration={duration},aecho=0.8:0.88:800:0.25,lowpass=f=500,volume=0.28" -filter_complex "[0:a][1:a]amix=inputs=2:duration=longest,apulsator=hz=0.15,volume=0.45,loudnorm=I=-16:TP=-1.5:LRA=11" -c:a libmp3lame -q:a 3 "{output}"'
        elif category == "epic_action":
            cmd = f'ffmpeg -y -f lavfi -i "sine=frequency=55:beep_factor=4:duration={duration},aecho=0.8:0.88:60:0.4,volume=0.38" -f lavfi -i "sine=frequency=110:beep_factor=6:duration={duration},aecho=0.8:0.9:120:0.3,volume=0.30" -filter_complex "[0:a][1:a]amix=inputs=2,lowpass=f=600,apulsator=hz=0.5,volume=0.50,loudnorm=I=-14" -c:a libmp3lame -q:a 3 "{output}"'
        elif category == "emotional":
            cmd = f'ffmpeg -y -f lavfi -i "sine=frequency=196:duration={duration},aecho=0.8:0.88:500:0.35,volume=0.32" -f lavfi -i "sine=frequency=261:duration={duration},aecho=0.8:0.9:600:0.3,volume=0.25" -filter_complex "[0:a][1:a]amix=inputs=2,lowpass=f=1200,volume=0.42" -c:a libmp3lame -q:a 3 "{output}"'
        elif category == "happy":
            cmd = f'ffmpeg -y -f lavfi -i "sine=frequency=196:duration={duration},apulsator=hz=0.8,volume=0.28" -f lavfi -i "sine=frequency=246:duration={duration},apulsator=hz=1.0,volume=0.22" -filter_complex "[0:a][1:a]amix=inputs=2,highpass=f=200,lowpass=f=2000,volume=0.40" -c:a libmp3lame -q:a 3 "{output}"'
        else:
            cmd = f'ffmpeg -y -f lavfi -i "sine=frequency=55:duration={duration},aecho=0.8:0.88:60:0.4,lowpass=f=800,volume=0.35" -f lavfi -i "sine=frequency=110:duration={duration},aecho=0.8:0.9:120:0.3,lowpass=f=1000,volume=0.28" -filter_complex "[0:a][1:a]amix=inputs=2,volume=0.45,loudnorm=I=-16" -c:a libmp3lame -q:a 3 "{output}"'
        subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if Path(output).exists() and Path(output).stat().st_size > 1000:
            print(f"BGM OK {Path(output).stat().st_size/1024:.1f} KB louder")
            return output
        cmd2 = f'ffmpeg -y -f lavfi -i "sine=frequency=80:duration={duration}" -c:a libmp3lame -q:a 9 -filter:a "volume=0.35,lowpass=f=500" "{output}"'
        subprocess.run(cmd2, shell=True, capture_output=True, timeout=20)
        if Path(output).exists():
            return output
    except Exception as e:
        print(f"BGM error {e}")
    return None

def ensure_bgm(output="bgm.mp3", movie=None, duration=60):
    try:
        genre_ids = movie.get("genre_ids", []) if movie else []
        category = "cinematic"
        if any(g in genre_ids for g in [27, 53, 9648, 80]):
            category = "suspense"
        elif any(g in genre_ids for g in [28, 12, 10752, 37, 10759]):
            category = "epic_action"
        elif any(g in genre_ids for g in [35, 16, 10751, 10762]):
            category = "happy"
        elif any(g in genre_ids for g in [10749, 18, 36]):
            category = "emotional"
        elif any(g in genre_ids for g in [878, 14, 10765]):
            category = "cinematic_futuristic"
        print(f"BGM Category: {category} Duration: {duration}s")
        return generate_local_cinematic_bgm(output, category, duration=duration)
    except Exception as e:
        print(f"BGM err {e}")
        return generate_local_cinematic_bgm(output, "cinematic", duration=duration)

def smart_trim_trailer_to_60s(input_path, output_path="trailer_60s.mp4"):
    try:
        dur = get_video_duration(input_path)
        print(f"Original trailer {dur:.1f}s")
        if Path(output_path).exists():
            Path(output_path).unlink()
        if dur <= 62:
            cmd = f'ffmpeg -y -i "{input_path}" -t 60 -c:v libx264 -preset fast -crf 23 -c:a aac "{output_path}"'
            subprocess.run(cmd, shell=True, capture_output=True, timeout=90)
            if Path(output_path).exists():
                return output_path
            return input_path
        target = 60
        current = 5.0
        segments = []
        seg_files = []
        keep_chunk = 10
        skip_chunk = 5
        while target > 0 and current < dur:
            keep = min(keep_chunk, target, dur - current)
            if keep <= 0:
                break
            end = current + keep
            seg_file = f"seg_{len(segments)}.mp4"
            seg_files.append(seg_file)
            cmd = f'ffmpeg -y -ss {current:.2f} -to {end:.2f} -i "{input_path}" -c:v libx264 -preset fast -crf 23 -c:a aac "{seg_file}"'
            subprocess.run(cmd, shell=True, capture_output=True, timeout=60)
            segments.append(seg_file)
            target -= keep
            current = end + skip_chunk
            if len(segments) >= 2:
                keep_chunk = 15
        if segments:
            with open("concat.txt", "w") as f:
                for sf in segments:
                    if Path(sf).exists():
                        f.write(f"file '{sf}'\n")
            cmd = f'ffmpeg -y -f concat -safe 0 -i concat.txt -c:v libx264 -preset fast -crf 23 -c:a aac "{output_path}"'
            subprocess.run(cmd, shell=True, capture_output=True, timeout=90)
            for sf in seg_files:
                if Path(sf).exists():
                    Path(sf).unlink()
            if Path("concat.txt").exists():
                Path("concat.txt").unlink()
            if Path(output_path).exists():
                print(f"Smart cut DONE {get_video_duration(output_path):.1f}s from {dur:.1f}s with {len(segments)} cuts")
                return output_path
        cmd = f'ffmpeg -y -ss 5 -i "{input_path}" -t 60 -c:v libx264 -preset fast -crf 23 -c:a aac "{output_path}"'
        subprocess.run(cmd, shell=True, capture_output=True, timeout=90)
        if Path(output_path).exists():
            return output_path
        return input_path
    except Exception as e:
        print(f"Smart trim err {e}")
        import traceback; traceback.print_exc()
        return input_path

def call_groq_fallback(movie_title, year, m_type, rating, overview, link, genre_str):
    if not GROQ_API_KEY or not GROQ_AVAILABLE:
        print("Groq not available")
        return None, None, None
    try:
        client = Groq(api_key=GROQ_API_KEY)
        title = movie_title
        prompt = f"""You are the Senior Bengali Voiceover Director for MoviMoon.
STRICT WORD COUNT: EXACTLY 165-170 Bengali words. Max 170, never over 170. 60 seconds voice.
Movie Title: {title} Year: {year} Rating: {rating}/10 Genre: {genre_str} Plot: {overview} Link: {link}
STRUCTURE: HOOK 28-30 words, STORY 55-60, ACTING 50-55, CTA 20-25 words. TOTAL 165-170.
RULES: Pure Bengali, no English. Say "মুভিমুন ডট অনলাইন" not "মুভিমুন অনলাইন ডট কম". In outro say "পুরো সিনেমাটি দেখতে ভিজিট করুন মুভিমুন ডট অনলাইন".
OUTPUT ONLY JSON: {{"voiceover": "165-170 words Bengali...", "bangla_title": "title", "caption": "...", "word_count": 168}}"""
        groq_models = ["llama-3.3-70b-specdec", "llama-3.3-70b-versatile", "meta-llama/llama-4-maverick-17b-128e-instruct", "meta-llama/llama-4-scout-17b-16e-instruct", "qwen/qwen3-32b", "moonshotai/kimi-k2-instruct", "llama3-70b-8192", "llama3-8b-8192", "openai/gpt-oss-20b", "openai/gpt-oss-120b"]
        completion = None
        last_err = None
        for gmodel in groq_models:
            try:
                print(f"Trying Groq model {gmodel}...")
                if "gpt-oss" in gmodel:
                    completion = client.chat.completions.create(model=gmodel, messages=[{"role": "user", "content": prompt}], temperature=1.0, max_tokens=3000)
                else:
                    completion = client.chat.completions.create(model=gmodel, messages=[{"role": "user", "content": prompt}], temperature=1.0, max_tokens=3000, response_format={"type": "json_object"})
                print(f"Groq model {gmodel} success")
                break
            except Exception as ge:
                print(f"Groq {gmodel} failed: {ge}")
                last_err = ge
                continue
        if not completion:
            raise Exception(f"All Groq models failed, last: {last_err}")
        content = completion.choices[0].message.content
        print(f"Groq raw: {content[:500]}")
        j = json.loads(content)
        voice = j.get("voiceover","").strip()
        story_bn = j.get("caption","").strip() or j.get("story_bn","").strip()
        wc = len(voice.split())
        if wc > 170:
            voice = " ".join(voice.split()[:170])
            wc = 170
        print(f"Groq SUCCESS - {wc} words")
        if not story_bn:
            story_bn = f"{overview[:100]} এক অসাধারণ গল্প!"
        return voice, story_bn, j.get("bangla_title", movie_title)
    except Exception as e:
        print(f"Groq error: {e}")
        import traceback; traceback.print_exc()
        return None, None, None

def call_gemini_video_script(title, year, m_type, rating, overview, link, movie=None):
    genre_str = get_genre_names(movie.get("genre_ids", []) if movie else [], english=True)
    title_raw = title
    if not GEMINI_API_KEY and not GROQ_API_KEY:
        story_bn = "এক অসাধারণ রহস্যময় গল্পের জগত!"
        voice = f"বন্ধুরা আজকে কথা বলবো {year} সালের সিনেমা {title_raw} নিয়ে।"
        return voice, story_bn, title_raw

    prompt = f"""You are the Senior Bengali Voiceover Director for MoviMoon.
CRITICAL WORD COUNT: EXACTLY 165-170 Bengali words. Max 170, never over 170. For 60 seconds.
If under 165 or over 170 = FAILURE.

INPUT: Movie Title: {title} Year: {year} Rating: {rating}/10 Genre: {genre_str} Plot: {overview} Link: {link}
STRUCTURE: HOOK 28-30 words, STORY 55-60, ACTING 50-55, CTA 20-25. TOTAL 165-170.
RULES: Pure Bengali, no English. Say "মুভিমুন ডট অনলাইন" not "মুভিমুন অনলাইন ডট কম". In outro MUST say "পুরো সিনেমাটি দেখতে ভিজিট করুন মুভিমুন ডট অনলাইন".
OUTPUT ONLY JSON: {{"voiceover": "165-170 words...", "bangla_title": "title", "caption": "...", "word_count": 168}}"""

    models = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]

    def smart_expand_to_limit(current_voice, current_wc, target_min=165, target_max=170):
        expansions = [
            "প্রতিটি দৃশ্য অসাধারণভাবে সাজানো হয়েছে।",
            "পরিচালকের মুন্সিয়ানা মুগ্ধ করবে।",
            "অভিনেতাদের দুর্দান্ত অভিনয় দেখবেন।",
            "সিনেমাটোগ্রাফি এবং আবহ সঙ্গীত প্রাণবন্ত।",
            "প্রতিটি মুহূর্তে টানটান উত্তেজনা রয়েছে।",
            "শেষের টুইস্টটা একেবারে অপ্রত্যাশিত।",
            "গল্পটা মন ছুঁয়ে যাবে।",
            "দেখতে ভুলবেন না।",
            "এই সিনেমাটি অবশ্যই দেখার মতো।",
            "আবেগ এবং রহস্যে ভরপুর।"
        ]
        result = current_voice
        cw = current_wc
        idx = 0
        while cw < target_min and idx < len(expansions):
            add = expansions[idx]
            new_wc = len((result + " " + add).split())
            if new_wc > target_max:
                idx += 1
                continue
            result = result + " " + add
            cw = new_wc
            idx += 1
        if cw > target_max:
            words = result.split()
            result = " ".join(words[:target_max])
            cw = target_max
        return result, cw

    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            data = {"contents":[{"parts":[{"text":prompt}]}], "generationConfig":{"temperature":0.7, "topP":0.9, "maxOutputTokens": 4096, "response_mime_type": "application/json"}}
            res = requests.post(url, json=data, timeout=30)
            if res.status_code == 200:
                js = res.json()
                try:
                    text = js["candidates"][0]["content"]["parts"][0]["text"]
                except:
                    print(f"{model} no text")
                    continue
                clean_text = text.replace("```json","").replace("```","").strip()
                m = re.search(r'\{.*\}', clean_text, re.DOTALL)
                if m:
                    j = json.loads(m.group())
                    voice = j.get("voiceover","").strip()
                    story_bn = j.get("caption","").strip() or j.get("story_bn","").strip()
                    wc = len(voice.split())
                    print(f"Gemini {model} OK - {wc} words story: {story_bn[:60]}")
                    if wc < 165:
                        current_voice = voice
                        current_wc = wc
                        loop_attempt = 1
                        max_loops = 3
                        while current_wc < 165 and loop_attempt <= max_loops:
                            print(f"Loop {loop_attempt}: Gemini gave only {current_wc} words, asking to expand previous to 165-170")
                            try:
                                expand_prompt = f"""You gave only {current_wc} words, need 165-170. Your previous text: {current_voice}
TASK: Expand to EXACTLY 165-170 Bengali words. Keep all content, add acting/direction/music. Current {current_wc} -> need 165-170.
MUST say "মুভিমুন ডট অনলাইন" not "মুভিমুন অনলাইন ডট কম".
OUTPUT ONLY JSON: {{"voiceover": "165-170 words...", "bangla_title": "title", "caption": "...", "word_count": 168}}"""
                                data_loop = {"contents":[{"parts":[{"text":expand_prompt}]}], "generationConfig":{"temperature":0.7, "topP":0.9, "maxOutputTokens": 4096, "response_mime_type": "application/json"}}
                                res_loop = requests.post(url, json=data_loop, timeout=30)
                                if res_loop.status_code == 200:
                                    js_loop = res_loop.json()
                                    text_loop = js_loop["candidates"][0]["content"]["parts"][0]["text"]
                                    clean_loop = text_loop.replace("```json","").replace("```","").strip()
                                    m_loop = re.search(r'\{.*\}', clean_loop, re.DOTALL)
                                    if m_loop:
                                        j_loop = json.loads(m_loop.group())
                                        voice_loop = j_loop.get("voiceover","").strip()
                                        wc_loop = len(voice_loop.split())
                                        print(f"Loop {loop_attempt} result: {current_wc} -> {wc_loop} words")
                                        if wc_loop >= 165 and wc_loop <= 170:
                                            print(f"Loop {loop_attempt} SUCCESS: {wc_loop} words")
                                            return voice_loop, story_bn, j_loop.get("bangla_title", title_raw)
                                        if wc_loop > 170:
                                            print(f"Loop {loop_attempt} too long {wc_loop} -> trimming to 170")
                                            voice_loop = " ".join(voice_loop.split()[:170])
                                            return voice_loop, story_bn, j_loop.get("bangla_title", title_raw)
                                        current_voice = voice_loop
                                        current_wc = wc_loop
                                        loop_attempt += 1
                                    else:
                                        loop_attempt += 1
                                else:
                                    loop_attempt += 1
                            except Exception as e:
                                print(f"Loop {loop_attempt} error: {e}")
                                loop_attempt += 1
                        if current_wc < 165:
                            print(f"After {max_loops} loops still {current_wc} words, fallback for remaining (cap 170)")
                            voice, wc = smart_expand_to_limit(current_voice, current_wc, 165, 170)
                            print(f"After fallback: {wc} words")
                        else:
                            voice = current_voice
                            wc = current_wc
                    if wc > 170:
                        print(f"Final trim {wc} -> 170")
                        voice = " ".join(voice.split()[:170])
                        wc = 170
                    if not story_bn:
                        story_bn = f"{overview[:120]} এক অসাধারণ গল্পের জগত!"
                    return voice, story_bn, j.get("bangla_title", title_raw)
                else:
                    print(f"{model} no JSON")
            else:
                print(f"Gemini {model} fail {res.status_code} {res.text[:200]}")
        except Exception as e:
            print(f"Gemini {model} err {e}")
            continue
    print("All Gemini models failed, trying Groq fallback...")
    groq_voice, groq_story, groq_title = call_groq_fallback(title_raw, year, m_type, rating, overview, link, genre_str)
    if groq_voice:
        return groq_voice, groq_story, groq_title
    story_bn = "এক অসাধারণ রহস্যময় গল্পের জগত!"
    voice = f"বন্ধুরা আজকে কথা বলবো {year} সালের সিনেমা {title_raw} নিয়ে।"
    return voice, story_bn, title_raw

def build_caption(title, year, m_type, genre_str, rating, story_bn, link):
    type_label = "Series" if m_type == "tv" else "Movie"
    if len(story_bn) > 100 or "#" in story_bn:
        story_text = story_bn
    else:
        story_text = f"📖 Story - {story_bn}\nএক অসাধারণ রহস্যময় গল্পের জগত!"
    caption = f"🎬 {type_label} - {title}({year})\n🎭 Genres - {genre_str}\n⭐ Rating - {rating}/10\n{story_text}\n🔗 ফুল মুভি লিংক: {link}\n👉 পুরো রিভিউ এবং ডাউনলোড পেতে ভিজিট করুন movimoon.online\n#MoviMoon #MovieReview #TrendingNow #MustWatch #BengaliReview #ViralReels\n#S #{title.replace(' ', '').replace('-', '')}"
    return caption

async def generate_tts_voice(text, output_path="voice.mp3"):
    print(f"TTS: {len(text.split())} words RATE +30% PRO STUDIO V28 HD 1080p")
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH, volume=VOLUME)
    await communicate.save(output_path)
    try:
        studio_path = output_path.replace(".mp3", "_studio.mp3")
        cmd = f'ffmpeg -y -i "{output_path}" -filter:a "highpass=f=85:width_type=o:width=1,lowpass=f=11000:width_type=o:width=1,acompressor=threshold=-18dB:ratio=4:attack=20:release=200:makeup=6dB,equalizer=f=3000:width_type=o:width=1.2:g=2.5,equalizer=f=8000:width_type=o:width=2:g=-2,equalizer=f=150:width_type=o:width=1:g=-1.5,loudnorm=I=-16:TP=-1.5:LRA=7:linear=true,volume=1.15" -c:a libmp3lame -q:a 0 -ar 48000 "{studio_path}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if Path(studio_path).exists() and Path(studio_path).stat().st_size > 1000:
            Path(studio_path).replace(output_path)
            print(f"PRO Studio voice applied - NO robotic {Path(output_path).stat().st_size/1024:.1f} KB")
        else:
            print(f"Studio failed, fallback: {result.stderr[-300:]}")
            fb = output_path.replace(".mp3", "_fb.mp3")
            subprocess.run(f'ffmpeg -y -i "{output_path}" -filter:a "highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11,volume=1.1" -c:a libmp3lame -q:a 1 "{fb}"', shell=True, capture_output=True, timeout=20)
            if Path(fb).exists():
                Path(fb).replace(output_path)
    except Exception as e:
        print(f"Studio effect err {e}")
        import traceback; traceback.print_exc()
    return output_path

def sanitize_drawtext(text):
    if not text:
        return "Movie"
    text = str(text)
    # Avoid problematic chars
    text = text.replace("'", " ").replace('"', " ").replace(":", " ").replace("\n", " ").replace("\r", " ")
    text = " ".join(text.split())
    if len(text) > 45:
        text = text[:42] + "..."
    return text.strip() or "Movie"

def create_9_16_hd_video(trailer_path, poster_path, voice_path, output="final.mp4", bgm_path=None, trailer_duration=60, title_text="MoviMoon"):
    try:
        if Path(output).exists():
            Path(output).unlink()
        has_bgm = bgm_path and Path(bgm_path).exists()
        if not has_bgm:
            bgm_path = generate_local_cinematic_bgm("bgm.mp3", "cinematic", duration=trailer_duration)
            has_bgm = Path(bgm_path).exists()
        dur = int(trailer_duration)
        safe_title = sanitize_drawtext(title_text)
        # FIX: Define font_path properly
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if not Path(font_path).exists():
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if not Path(font_path).exists():
                font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        print(f"Creating {dur}s video FINAL V28 HD 1080p ZOOM 65% - Title: {safe_title} Font: {font_path} Exists:{Path(font_path).exists()}")
        if poster_path and Path(poster_path).exists():
            cmd = (
                f"ffmpeg -y -loop 1 -t {dur} -i \"{poster_path}\" "
                f"-i \"{trailer_path}\" -i \"{voice_path}\" -stream_loop -1 -i \"{bgm_path}\" "
                f"-filter_complex \"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=22:steps=3,setsar=1,trim=duration={dur}[bg];"
                f"[1:v]scale=1080:1248:force_original_aspect_ratio=increase,crop=1080:1248,setsar=1[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=0,scale=1080:1920:flags=lanczos[base0];"
                f"[base0]drawtext=text='{safe_title}':fontcolor=white:fontsize=66:box=1:boxcolor=black@0.75:boxborderw=16:borderw=4:bordercolor=black:"
                f"x=(w-text_w)/2:y=120+4*sin(t*1.8):shadowcolor=black:shadowx=4:shadowy=4:fontfile={font_path}[base1];"
                f"[base1]drawtext=text='{safe_title}':fontcolor=white@0.25:fontsize=66:x=(w-text_w)/2+2:y=122+4*sin(t*1.8):fontfile={font_path}[base_top];"
                f"[base_top]drawtext=text='movimoon.online':fontcolor=yellow:fontsize=52:box=1:boxcolor=black@0.75:boxborderw=14:borderw=3:bordercolor=black:"
                f"x=(w-text_w)/2:y=h-160-4*sin(t*2.2):shadowcolor=black:shadowx=3:shadowy=3:fontfile={font_path}[final_v];"
                f"[1:a]volume=0.30[trailer_low];[3:a]volume=0.40[bg_vol];[2:a]asplit=2[voice_sc][voice_mix];"
                f"[bg_vol][voice_sc]sidechaincompress=threshold=0.015:ratio=8:attack=20:release=400:makeup=1[ducked];"
                f"[trailer_low][ducked][voice_mix]amix=inputs=3:duration=longest:dropout_transition=0:weights=0.30 0.35 1,volume=1.25,loudnorm=I=-16:TP=-1.5:LRA=8[a]\" "
                f"-map \"[final_v]\" -map \"[a]\" -c:v libx264 -profile:v high -level:v 4.2 -preset slow -crf 16 -pix_fmt yuv420p -r 30 -movflags +faststart -c:a aac -b:a 192k -t {dur} \"{output}\""
            )
        else:
            cmd = (
                f"ffmpeg -y -i \"{trailer_path}\" -i \"{voice_path}\" -stream_loop -1 -i \"{bgm_path}\" "
                f"-filter_complex \"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=22:steps=3[bg];"
                f"[0:v]scale=1080:1248:force_original_aspect_ratio=increase,crop=1080:1248[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,scale=1080:1920:flags=lanczos[base0];"
                f"[base0]drawtext=text='{safe_title}':fontcolor=white:fontsize=66:box=1:boxcolor=black@0.75:boxborderw=16:borderw=4:bordercolor=black:"
                f"x=(w-text_w)/2:y=120+4*sin(t*1.8):shadowcolor=black:shadowx=4:shadowy=4:fontfile={font_path}[base1];"
                f"[base1]drawtext=text='{safe_title}':fontcolor=white@0.25:fontsize=66:x=(w-text_w)/2+2:y=122+4*sin(t*1.8):fontfile={font_path}[base_top];"
                f"[base_top]drawtext=text='movimoon.online':fontcolor=yellow:fontsize=52:box=1:boxcolor=black@0.75:boxborderw=14:borderw=3:bordercolor=black:"
                f"x=(w-text_w)/2:y=h-160-4*sin(t*2.2):shadowcolor=black:shadowx=3:shadowy=3:fontfile={font_path}[final_v];"
                f"[0:a]volume=0.30[trailer_low];[2:a]volume=0.40[bg_vol];[1:a]asplit=2[voice_sc][voice_mix];"
                f"[bg_vol][voice_sc]sidechaincompress=threshold=0.015:ratio=8:attack=20:release=400:makeup=1[ducked];"
                f"[trailer_low][ducked][voice_mix]amix=inputs=3:duration=longest:dropout_transition=0:weights=0.30 0.35 1,volume=1.25,loudnorm=I=-16:TP=-1.5:LRA=8[a]\" "
                f"-map \"[final_v]\" -map \"[a]\" -c:v libx264 -profile:v high -level:v 4.2 -preset slow -crf 16 -pix_fmt yuv420p -r 30 -movflags +faststart -c:a aac -b:a 192k -t {dur} \"{output}\""
            )
        print(f"FFmpeg FINAL V28 HD {dur}s...")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=240)
        if Path(output).exists() and Path(output).stat().st_size > 50000:
            print(f"Final OK V25 {Path(output).stat().st_size/1024/1024:.2f} MB - ZOOM 65% + 165-170 + TRAILER ONLY")
            return output
        print(f"FFmpeg err {result.stderr[-1500:]}")
        fallback_cmd = (
            f'ffmpeg -y -loop 1 -t {dur} -i "{poster_path}" -i "{trailer_path}" -i "{voice_path}" -stream_loop -1 -i "{bgm_path}" '
            f'-filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=20[bg];[1:v]scale=1080:1248:force_original_aspect_ratio=increase,crop=1080:1248[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[base];[1:a]volume=0.30[tl];[3:a]volume=0.30[bgv];[2:a]volume=1.0[vo];[tl][bgv][vo]amix=inputs=3:duration=longest:weights=0.30 0.30 1,volume=1.2[a]" '
            f'-map "[base]" -map "[a]" -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -r 30 -movflags +faststart -c:a aac -b:a 192k -t {dur} "{output}"'
        ) if poster_path and Path(poster_path).exists() else (
            f'ffmpeg -y -i "{trailer_path}" -i "{voice_path}" -stream_loop -1 -i "{bgm_path}" '
            f'-filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=20[bg];[0:v]scale=1080:1248:force_original_aspect_ratio=increase,crop=1080:1248[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[base];[0:a]volume=0.30[tl];[2:a]volume=0.30[bgv];[1:a]volume=1.0[vo];[tl][bgv][vo]amix=inputs=3:duration=longest:weights=0.30 0.30 1,volume=1.2[a]" '
            f'-map "[base]" -map "[a]" -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -r 30 -movflags +faststart -c:a aac -b:a 192k -t {dur} "{output}"'
        )
        subprocess.run(fallback_cmd, shell=True, capture_output=True, timeout=240)
        if Path(output).exists():
            return output
        return None
    except Exception as e:
        print(f"V28 Error {e}")
        import traceback; traceback.print_exc()
        return None


def build_youtube_seo_metadata(title, year, m_type, genre_str, rating, story_bn, link, bangla_title, overview):
    """Build SEO-friendly YouTube Shorts title, description, tags"""
    # Clean title for SEO
    en_title = title.strip()
    bn_title = bangla_title.strip() if bangla_title else en_title
    
    # Type label
    type_label = "Movie" if m_type == "movie" else "Web Series"
    type_bn = "সিনেমা" if m_type == "movie" else "সিরিজ"
    
    # SEO Title: 100 chars max, include keywords
    # Format: Bengali Title | English Title (Year) Explained #Shorts
    # Fallback if too long
    base_title = f"{bn_title} | {en_title} ({year})"
    if len(base_title) > 70:
        base_title = f"{en_title} ({year})"
    if len(base_title) > 80:
        base_title = base_title[:80]
    yt_title = f"{base_title} Explained #Shorts"
    if len(yt_title) > 100:
        yt_title = f"{en_title} ({year}) #Shorts"
    yt_title = yt_title[:100]
    
    # SEO Description - 5000 chars max, keyword rich
    genre_keywords = genre_str.replace(", ", ", ") if genre_str else "Drama"
    hashtags = f"#Shorts #{en_title.replace(' ', '')} #{type_label} #MoviMoon #MovieReview #BengaliReview #Hollywood #Bollywood #New{type_label}{year} #Trending{type_label}"
    
    description = f"""🎬 {en_title} ({year}) - {type_label} Review & Story Explained in Bengali

{story_bn}

📖 Full Story:
{overview[:300] if overview else f"An extraordinary {genre_keywords} story that will touch your heart."}

🎭 Genre: {genre_keywords}
⭐ Rating: {rating}/10
📅 Year: {year}

🔗 Watch Full Details: {link}
🌐 Website: https://movimoon.online

👉 এই {type_bn}টি কেমন লাগলো কমেন্টে জানান!
👉 এরকম আরো {type_bn} রিভিউ পেতে চ্যানেলটি সাবস্ক্রাইব করুন

{hashtags}

#movimoon #movimoononline #banglamoviereview #moviereviewbengali #newmovie{year} #upcomingmovie #moviereview

---
Disclaimer: This video uses trailer clips under fair use for review purposes. All rights belong to respective owners.
"""
    # Trim description to 4500 chars (YT limit 5000)
    if len(description) > 4500:
        description = description[:4500]
    
    # SEO Tags - max 500 chars total, 15 tags
    tags = []
    tags.append(en_title.lower())
    tags.append(bn_title.lower())
    tags.append(f"{en_title} {year}")
    tags.append(f"{en_title} trailer")
    tags.append(f"{en_title} review")
    tags.append(f"{en_title} explained")
    tags.append(f"{en_title} bengali")
    tags.append(genre_keywords.lower())
    tags.append(f"{type_label.lower()} {year}")
    tags.append(f"new {type_label.lower()} {year}")
    tags.append(f"{type_label.lower()} review bengali")
    tags.append("movimoon")
    tags.append("movimoon.online")
    tags.append("bengali movie review")
    tags.append("shorts")
    # Clean tags
    clean_tags = []
    for t in tags:
        t = t.strip().lower()
        t = t[:30]  # tag max 30 chars
        if t and len(t) > 1 and t not in clean_tags:
            clean_tags.append(t)
    clean_tags = clean_tags[:15]
    
    return yt_title, description, clean_tags


def upload_video_to_youtube(video_path, yt_title, yt_description, yt_tags):
    """Upload video to YouTube Shorts using Data API v3 - SEO optimized"""
    if not YOUTUBE_CLIENT_ID or not YOUTUBE_CLIENT_SECRET or not YOUTUBE_REFRESH_TOKEN:
        print("⚠️ YouTube credentials not set (YOUTUBE_CLIENT_ID/SECRET/REFRESH_TOKEN), skipping YouTube upload")
        return None
    
    try:
        print(f"Uploading to YouTube Shorts: {yt_title} - {Path(video_path).stat().st_size/1024/1024:.2f} MB")
        # Import here to not break if not installed
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError as ie:
            print(f"YouTube libraries not installed: {ie}, installing...")
            subprocess.check_call(["pip", "install", "google-api-python-client", "google-auth", "google-auth-oauthlib", "google-auth-httplib2"])
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        
        creds = Credentials(
            None,
            refresh_token=YOUTUBE_REFRESH_TOKEN,
            client_id=YOUTUBE_CLIENT_ID,
            client_secret=YOUTUBE_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/youtube.upload"]
        )
        
        youtube = build('youtube', 'v3', credentials=creds)
        
        # Media upload
        media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
        
        body = {
            "snippet": {
                "title": yt_title,
                "description": yt_description,
                "tags": yt_tags,
                "categoryId": "24",  # Entertainment
                "defaultLanguage": "bn",
                "defaultAudioLanguage": "bn"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
                "madeForKids": False
            }
        }
        
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"YouTube upload {int(status.progress()*100)}%")
        
        print(f"✅ YOUTUBE SHORTS UPLOADED - ID: {response.get('id')} - https://youtube.com/shorts/{response.get('id')}")
        return response
        
    except Exception as e:
        print(f"❌ YouTube Upload Error: {e}")
        import traceback; traceback.print_exc()
        # Quota check
        if "quota" in str(e).lower():
            print("⚠️ YouTube quota exceeded (100/day limit). Will retry next run.")
        return None


def upload_video_to_facebook(page_id, token, video_path, caption, label):
    try:
        print(f"Uploading {label} - {Path(video_path).stat().st_size/1024/1024:.2f} MB")
        url = f"https://graph.facebook.com/v18.0/{page_id}/videos"
        with open(video_path, 'rb') as f:
            files = {'source': f}
            data = {'description': caption, 'access_token': token}
            r = requests.post(url, files=files, data=data, timeout=300)
            print(f"FB Upload {label} Status {r.status_code} {r.text[:500]}")
            if r.status_code == 200:
                return r.json()
        return None
    except Exception as e:
        print(f"FB Upload Error {e}")
        import traceback; traceback.print_exc()
        return None

async def main():
    print("=== MoviMoon AutoPoster V29 HD 1080p FB+YT START ===")
    history = load_history()
    movies = get_trending_mixed()
    if not movies:
        print("No movies found")
        return
    for idx, movie in enumerate(movies[:10], 1):
        try:
            tmdb_id = str(movie['id'])
            if is_already_posted(tmdb_id, history):
                print(f"[{idx}/10] Already posted {tmdb_id}, skipping")
                continue
            title = movie.get('title') or movie.get('name') or 'Unknown'
            title_raw = title
            print(f">>> [{idx}/10] {title} ({tmdb_id})")
            date_str = movie.get('release_date') or movie.get('first_air_date') or ''
            year = date_str[:4] if date_str else str(datetime.now().year)
            m_type = movie.get('media_type','movie')
            rating = movie.get('vote_average', 7.0)
            overview = movie.get('overview','') or 'An extraordinary story.'
            genre_ids = movie.get('genre_ids', [])
            genre_str = get_genre_names(genre_ids)
            link = f"https://movimoon.online/movie/{tmdb_id}-{slugify(title)}" if m_type=='movie' else f"https://movimoon.online/tv/{tmdb_id}-{slugify(title)}"
            youtube_url, yt_key = get_youtube_trailer(movie)
            if not youtube_url:
                print(f"No trailer for {title}, skipping")
                continue
            print(f"Trailer URL: {youtube_url}")
            trailer_file = download_trailer(youtube_url, "trailer.mp4")
            if not trailer_file:
                print(f"Trailer download failed for {title}")
                continue
            poster_file = download_movie_poster(movie, "poster.jpg")
            voice_text, story_bn, bangla_title = call_gemini_video_script(title, year, m_type, rating, overview, link, movie)
            wc = len(voice_text.split())
            if wc > 170:
                voice_text = " ".join(voice_text.split()[:170])
                wc = 170
                print(f"Trimmed voice to 170 words for 60s (was {len(voice_text.split())} -> 170)")
            if wc < 165:
                print(f"WARNING: Voice still {wc} words < 165, adding fallback")
                # quick fallback add
                voice_text = voice_text + " এই সিনেমাটি অবশ্যই দেখার মতো। গল্পটা মন ছুঁয়ে যাবে।"
                voice_text = " ".join(voice_text.split()[:170])
                wc = len(voice_text.split())
            print(f"Voice {wc} words (target 165-170)")
            caption = build_caption(title, year, m_type, genre_str, rating, story_bn, link)
            print(f"Caption built: {caption[:200]}")
            await generate_tts_voice(voice_text, "voice.mp3")
            trailer_dur = get_video_duration(trailer_file)
            trailer_60s = smart_trim_trailer_to_60s(trailer_file, "trailer_60s.mp4")
            trailer_dur = get_video_duration(trailer_60s)
            bgm_file = ensure_bgm("bgm.mp3", movie, duration=int(trailer_dur))
            final_video = create_9_16_hd_video(trailer_60s, poster_file, "voice.mp3", "final.mp4", bgm_path=bgm_file, trailer_duration=int(trailer_dur), title_text=title_raw)
            if not final_video or not Path(final_video).exists():
                print(f"Final video creation failed for {title}")
                continue
            fb_result = upload_video_to_facebook(FB_PAGE_ID, FB_PAGE_TOKEN, final_video, caption, title)
            if fb_result:
                # V29: PAGE POSTED = WORKFLOW DONE, no 2nd try + YT SHORTS OPTIONAL
                print(f"✅ PAGE POSTED SUCCESSFULLY - ID: {fb_result.get('id','unknown')}")
                history[tmdb_id] = datetime.now().isoformat()
                save_history(history)
                print(f"Posted {title} successfully - PAGE ONLY SUCCESS = WORK DONE")
                # GROUP OPTIONAL - fail holeo page success = done
                if FB_GROUP_ID and FB_GROUP_ID.strip():
                    try:
                        print(f"Attempting optional group post for {FB_GROUP_ID}...")
                        group_result = upload_video_to_facebook(FB_GROUP_ID, FB_PAGE_TOKEN, final_video, caption, f"{title}")
                        if group_result:
                            print(f"✅ GROUP ALSO POSTED - ID: {group_result.get('id','unknown')}")
                        else:
                            print(f"⚠️ Group failed but PAGE SUCCESS - WORK DONE")
                    except Exception as ge:
                        print(f"⚠️ Group error ignored: {ge} - PAGE SUCCESS = WORK DONE")
                else:
                    print(f"No FB_GROUP_ID, PAGE ONLY mode")
                
                # YOUTUBE SHORTS OPTIONAL - SEO Optimized - fail holeo page success = done
                try:
                    print(f"Building YouTube SEO metadata for {title}...")
                    yt_title, yt_description, yt_tags = build_youtube_seo_metadata(title, year, m_type, genre_str, rating, story_bn, link, bangla_title, overview)
                    print(f"YouTube Title: {yt_title}")
                    print(f"YouTube Tags: {', '.join(yt_tags[:5])}...")
                    yt_result = upload_video_to_youtube(final_video, yt_title, yt_description, yt_tags)
                    if yt_result:
                        print(f"✅ YOUTUBE SHORTS ALSO POSTED - https://youtube.com/shorts/{yt_result.get('id')}")
                    else:
                        print(f"⚠️ YouTube upload failed/skip but PAGE SUCCESS - WORK DONE")
                except Exception as ye:
                    print(f"⚠️ YouTube error ignored: {ye} - PAGE SUCCESS = WORK DONE")
                
                # Cleanup
                for f in ["trailer.mp4", "trailer_60s.mp4", "poster.jpg", "voice.mp3", "bgm.mp3", "final.mp4"]:
                    try:
                        if Path(f).exists():
                            Path(f).unlink()
                    except:
                        pass
                print(f"🎉 1 VIDEO DONE - FB + YT (optional) - WORKFLOW COMPLETE - STOPPING, NO 2nd TRY")
                break
            else:
                print(f"Failed to post {title}")
            # Cleanup for failed case
            for f in ["trailer.mp4", "trailer_60s.mp4", "poster.jpg", "voice.mp3", "bgm.mp3", "final.mp4"]:
                try:
                    if Path(f).exists():
                        Path(f).unlink()
                except:
                    pass
            print(f"Waiting 10s before next...")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"Error processing movie {movie.get('id')}: {e}")
            import traceback; traceback.print_exc()
            continue
    print("=== MoviMoon AutoPoster V29 END ===")

if __name__ == "__main__":
    asyncio.run(main())
