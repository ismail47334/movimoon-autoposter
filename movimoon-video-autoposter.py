import os, requests, random, re, time, asyncio, json, subprocess
from datetime import datetime, timedelta
from pathlib import Path

print("=== MoviMoon Bot - MASTER V13 GROQ+GEMINI 165WORDS FIX ===")

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
            print(f"Strategy {i} failed")
            Path(output).unlink(missing_ok=True)
        except subprocess.TimeoutExpired:
            print(f"Strategy {i} TIMEOUT")
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
        groq_prompt = f"You are Senior Bengali Voiceover Director for MoviMoon. MUST write 165-180 Bengali words. INPUT Title {movie_title} Year {year} Rating {rating}/10 Genre {genre_str} Plot {overview} Link {link}. STRUCTURE HOOK 30 words, PLOT 60 words 5 sentences, ACTING 55 words 4 sentences, CTA 30 words. Total 175 words TARGET. LANGUAGE 100% Pure Bengali using । , ! ?. OUTPUT JSON ONLY with voiceover 175 words Bengali, story_bn 30 words, bangla_title."
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": groq_prompt}],
            temperature=1.0,
            max_tokens=3000,
            response_format={"type": "json_object"}
        )
        content = completion.choices[0].message.content
        print(f"Groq raw: {content[:500]}")
        j = json.loads(content)
        voice = j.get("voiceover","").strip()
        story_bn = j.get("story_bn","").strip()
        wc = len(voice.split())
        print(f"Groq SUCCESS - {wc} words")
        if wc < 100:
            print(f"Groq short {wc}, expanding")
            voice = voice + " এই সিনেমার প্রতিটি দৃশ্য অসাধারণভাবে সাজানো হয়েছে। পরিচালকের মুন্সিয়ানা এবং অভিনেতাদের দুর্দান্ত অভিনয় আপনাকে মুগ্ধ করবে। গল্পের প্রতিটি মোড়ে রয়েছে চমক এবং উত্তেজনা। শেষ পর্যন্ত দেখার মতো একটি দুর্দান্ত সিনেমা। এখনই দেখুন মুভিমুনে ভিজিট করে।"
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
        story_bn = "এক অসাধারণ রহস্যময় গল্পের জগত! বাবার মৃত্যুর পর এক তরুণী নানা প্রতিকূলতার মুখোমুখি হয়।"
        voice = f"বন্ধুরা কেমন আছেন সবাই আজকে কথা বলবো {year} সালের আলোচিত সিনেমা নিয়ে। এই সিনেমার গল্পটা এতটাই টানটান উত্তেজনায় ভরা যে একবার দেখা শুরু করলে শেষ না করে উঠতে পারবেন না। প্রধান চরিত্রের অসাধারণ অভিনয় দুর্দান্ত পরিচালনা এবং আবহ সঙ্গীত আপনাকে এক মুহূর্তের জন্যও বিরক্ত হতে দেবে না। বিশেষ করে গল্পের শেষের চমকটা আপনার মাথা ঘুরিয়ে দেবে। যারা রোমাঞ্চ এবং অ্যাকশন পছন্দ করেন তাদের জন্য এটা অবশ্যই দেখার মতো একটি সিনেমা। পুরো সিনেমাটির বিস্তারিত রিভিউ পেয়ে যাবেন আমাদের ওয়েবসাইট মুভিমুন ডট অনলাইন এ। এখনই ভিজিট করুন। বন্ধুরা এই সিনেমাটি কিন্তু আপনাদের মন ছুঁয়ে যাবে। এই গল্পের প্রতিটা মুহূর্ত আপনাকে আটকে রাখবে শেষ পর্যন্ত।"
        return voice, story_bn, title_raw

    gemini_prompt = f"You are the Senior Bengali Voiceover Director for MoviMoon. You MUST write 165-180 Bengali words. Shorter than 165 is FAILURE - audio will fail. CRITICAL: Count words. Need 175 words. INPUT Movie {title_raw} Year {year} Rating {rating}/10 Genre {genre_str} Plot {overview} Link {link}. WRITE 4 PARAGRAPHS Paragraph1 HOOK 30 words energetic opening with movie name. Paragraph2 PLOT 60 words detailed story 5 sentences no spoilers. Paragraph3 ACTING 55 words performance direction music cinematography climax 4 sentences. Paragraph4 CTA 30 words rating mention watch on MoviMoon. LANGUAGE 100 percent Pure Bengali using । , ! ?. Also provide story_bn 30 words Bengali story summary. OUTPUT ONLY JSON with voiceover 175 words Bengali text, bangla_title Bengali title, story_bn 30 words, word_count 175."

    models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.0-flash-lite", "gemini-flash-latest"]
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            data = {"contents":[{"parts":[{"text":gemini_prompt}]}], "generationConfig":{"temperature":1.0, "topP":0.95, "topK":40, "maxOutputTokens": 4096}}
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
                    story_bn = j.get("story_bn","").strip()
                    wc = len(voice.split())
                    print(f"Gemini {model} OK - {wc} words story: {story_bn[:60]}")
                    if wc < 140:
                        print(f"Too short {wc} - required 165, skipping")
                        continue
                    if wc < 165:
                        print(f"Borderline {wc}, expanding with extra sentences")
                        voice = voice + " এই সিনেমার প্রতিটি মুহূর্ত আপনাকে আটকে রাখবে। অসাধারণ সিনেমাটোগ্রাফি এবং আবহ সঙ্গীত গল্পটিকে আরও প্রাণবন্ত করে তুলেছে। শেষের টুইস্টটা একেবারে অপ্রত্যাশিত।"
                    if not story_bn or len(story_bn.split()) < 8:
                        story_bn = f"{overview[:120]} এক অসাধারণ গল্পের জগত!"
                    return voice, story_bn, j.get("bangla_title", title_raw)
                else:
                    print(f"{model} no JSON")
            else:
                print(f"Gemini {model} fail {res.status_code} {res.text[:200]}")
        except Exception as e:
            print(f"Gemini {model} err {e}")
            continue

    print("All Gemini models failed, trying Groq llama-3.3-70b-versatile fallback...")
    groq_voice, groq_story, groq_title = call_groq_fallback(title_raw, year, m_type, rating, overview, link, genre_str)
    if groq_voice:
        return groq_voice, groq_story, groq_title

    story_bn = "এক অসাধারণ রহস্যময় গল্পের জগত! প্রতিটা মুহূর্তে টানটান উত্তেজনা।"
    voice = f"বন্ধুরা আজকে কথা বলবো {year} সালের সিনেমা {title_raw} নিয়ে। এই সিনেমার গল্পটা এতটাই অসাধারণ যে একবার দেখা শুরু করলে শেষ না করে উঠতে পারবেন না। প্রধান চরিত্রের অভিনয় এবং পরিচালনা দুর্দান্ত। গল্পের প্রতিটি মোড়ে রয়েছে চমক। প্রধান অভিনেতার অসাধারণ পারফরম্যান্স আপনাকে মুগ্ধ করবে। পরিচালকের মুন্সিয়ানা এবং সিনেমাটোগ্রাফি অসাধারণ। আবহ সঙ্গীত গল্পটিকে আরও প্রাণবন্ত করে তুলেছে। বিশেষ করে শেষের চমকটা আপনার মাথা ঘুরিয়ে দেবে। যারা থ্রিলার এবং ড্রামা পছন্দ করেন তাদের জন্য এটা অবশ্যই দেখার মতো। পুরো রিভিউ পেতে ভিজিট করুন মুভিমুন ডট অনলাইন। এই সিনেমাটি আপনাদের মন ছুঁয়ে যাবে। প্রতিটা মুহূর্ত টানটান উত্তেজনায় ভরা। এখনই দেখুন।"
    return voice, story_bn, title_raw

def build_caption(title, year, m_type, genre_str, rating, story_bn, link):
    type_label = "Series" if m_type == "tv" else "Movie"
    caption = f"🎬 {type_label} - {title}({year})\n🎭 Genres - {genre_str}\n⭐ Rating - {rating}/10\n📖 Story - {story_bn}\nএক অসাধারণ রহস্যময় গল্পের জগত!\n🔗 ফুল মুভি লিংক: {link}\n👉 পুরো রিভিউ এবং ডাউনলোড পেতে ভিজিট করুন movimoon.online\n#MoviMoon #MovieReview #TrendingNow #MustWatch #BengaliReview #ViralReels\n#S #{title.replace(' ', '').replace('-', '')}"
    return caption

async def generate_tts_voice(text, output_path="voice.mp3"):
    print(f"TTS: {len(text.split())} words RATE +28% PRO STUDIO V13 NO ROBOTIC")
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

def create_9_16_hd_video(trailer_path, poster_path, voice_path, output="final.mp4", bgm_path=None, trailer_duration=60):
    try:
        if Path(output).exists():
            Path(output).unlink()
        has_bgm = bgm_path and Path(bgm_path).exists()
        if not has_bgm:
            bgm_path = generate_local_cinematic_bgm("bgm.mp3", "cinematic", duration=trailer_duration)
            has_bgm = Path(bgm_path).exists()
        dur = int(trailer_duration)
        print(f"Creating {dur}s video V13 SIDECHAIN DUCKING - BGM auto ducks when voice speaks")
        if poster_path and Path(poster_path).exists():
            cmd = (
                f'ffmpeg -y -loop 1 -t {dur} -i "{poster_path}" '
                f'-i "{trailer_path}" -i "{voice_path}" -stream_loop -1 -i "{bgm_path}" '
                f'-filter_complex "'
                f'[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=20:steps=2,setsar=1,trim=duration={dur}[bg];'
                f'[1:v]scale=1080:800:force_original_aspect_ratio=increase,crop=1080:800[fg];'
                f'[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1:format=auto,scale=1080:1920:flags=lanczos[base];'
                f'[1:a]volume=0.08[trailer_low];'
                f'[3:a]volume=0.40[bg_vol];'
                f'[2:a]asplit=2[voice_sc][voice_mix];'
                f'[bg_vol][voice_sc]sidechaincompress=threshold=0.015:ratio=8:attack=20:release=400:makeup=1[ducked];'
                f'[trailer_low][ducked][voice_mix]amix=inputs=3:duration=longest:dropout_transition=0:weights=0.08 0.35 1,volume=1.25,loudnorm=I=-16:TP=-1.5:LRA=8[a]" '
                f'-map "[base]" -map "[a]" '
                f'-c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -r 30 '
                f'-c:a aac -b:a 192k -t {dur} "{output}"'
            )
        else:
            cmd = (
                f'ffmpeg -y -i "{trailer_path}" -i "{voice_path}" -stream_loop -1 -i "{bgm_path}" '
                f'-filter_complex "'
                f'[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=20:steps=2[bg];'
                f'[0:v]scale=1080:800:force_original_aspect_ratio=increase,crop=1080:800[fg];'
                f'[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,scale=1080:1920:flags=lanczos[base];'
                f'[0:a]volume=0.08[trailer_low];'
                f'[2:a]volume=0.40[bg_vol];'
                f'[1:a]asplit=2[voice_sc][voice_mix];'
                f'[bg_vol][voice_sc]sidechaincompress=threshold=0.015:ratio=8:attack=20:release=400:makeup=1[ducked];'
                f'[trailer_low][ducked][voice_mix]amix=inputs=3:duration=longest:dropout_transition=0:weights=0.08 0.35 1,volume=1.25,loudnorm=I=-16:TP=-1.5:LRA=8[a]" '
                f'-map "[base]" -map "[a]" '
                f'-c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p -r 30 '
                f'-c:a aac -b:a 192k -t {dur} "{output}"'
            )
        print(f"FFmpeg V13 SIDECHAIN DUCKING {dur}s...")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=180)
        if Path(output).exists() and Path(output).stat().st_size > 50000:
            print(f"Final OK V13 {Path(output).stat().st_size/1024/1024:.2f} MB {get_video_duration(output):.1f}s - Voice clear, BGM ducks automatically")
            return output
        print(f"FFmpeg err {result.stderr[-1000:]}")
        fallback_cmd = (
            f'ffmpeg -y -loop 1 -t {dur} -i "{poster_path}" -i "{trailer_path}" -i "{voice_path}" -stream_loop -1 -i "{bgm_path}" '
            f'-filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=18[bg];[1:v]scale=1080:800[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[base];[1:a]volume=0.08[tl];[3:a]volume=0.30[bgv];[2:a]volume=1.0[vo];[tl][bgv][vo]amix=inputs=3:duration=longest:weights=0.08 0.30 1,volume=1.2[a]" '
            f'-map "[base]" -map "[a]" -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k -t {dur} "{output}"'
        ) if poster_path and Path(poster_path).exists() else (
            f'ffmpeg -y -i "{trailer_path}" -i "{voice_path}" -stream_loop -1 -i "{bgm_path}" '
            f'-filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=18[bg];[0:v]scale=1080:800[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[base];[0:a]volume=0.08[tl];[2:a]volume=0.30[bgv];[1:a]volume=1.0[vo];[tl][bgv][vo]amix=inputs=3:duration=longest:weights=0.08 0.30 1,volume=1.2[a]" '
            f'-map "[base]" -map "[a]" -c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k -t {dur} "{output}"'
        )
        subprocess.run(fallback_cmd, shell=True, capture_output=True, timeout=180)
        if Path(output).exists():
            return output
        return None
    except Exception as e:
        print(f"V13 Error {e}")
        import traceback; traceback.print_exc()
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
    print("=== MAIN START V13 GROQ+GEMINI 165WORDS FIX ===")
    history = load_history()
    items = get_trending_mixed()
    print(f"Found {len(items)} items")
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
            year = (movie.get("release_date") or movie.get("first_air_date") or "2025")[:4]
            rating = round(movie.get("vote_average",0), 1)
            overview = movie.get("overview","")[:800]
            link, m_type = build_movimoon_link(movie)
            genre_en = get_genre_names(movie.get("genre_ids", []), english=True)
            voice_text, story_bn, bangla_title = call_gemini_video_script(title_raw, year, m_type, rating, overview, link, movie=movie)
            if not voice_text:
                print(f"Gemini failed")
                continue
            caption = build_caption(title_raw, year, m_type, genre_en, rating, story_bn, link)
            print(f"Caption built:\n{caption[:300]}")
            trailer_file = download_trailer(yt_url, "trailer.mp4")
            if not trailer_file:
                print(f"Trailer download failed")
                continue
            poster_file = download_movie_poster(movie, "poster.jpg")
            trailer_60s = smart_trim_trailer_to_60s(trailer_file, "trailer_60s.mp4")
            trailer_dur = get_video_duration(trailer_60s)
            print(f"Trailer final {trailer_dur:.1f}s")
            bgm_file = ensure_bgm("bgm.mp3", movie=movie, duration=int(trailer_dur))
            asyncio.run(generate_tts_voice(voice_text, "voice.mp3"))
            print(f"Voice {get_video_duration('voice.mp3'):.1f}s Trailer {trailer_dur:.1f}s BGM {get_video_duration(bgm_file):.1f}s")
            final_video = create_9_16_hd_video(trailer_60s, poster_file, "voice.mp3", "final.mp4", bgm_path=bgm_file, trailer_duration=int(trailer_dur))
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
            for f in ["trailer.mp4","trailer_60s.mp4","voice.mp3","final.mp4","poster.jpg","bgm.mp3","seg_0.mp4","seg_1.mp4","seg_2.mp4","seg_3.mp4","seg_4.mp4","seg_5.mp4","concat.txt"]:
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
