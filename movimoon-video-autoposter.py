import os, requests, random, re, time, asyncio, json, subprocess
from datetime import datetime, timedelta
from pathlib import Path

print("=== MoviMoon Bot - FINAL V40 SELECT-FILTER 1440p SMART-CUT | DYNAMIC WORDS + 2-LINE TITLE + FB + YT SHORTS ===")

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
    print(f"YT-DLP V40 START - V28 STYLE + BOT BYPASS {youtube_url}")
    Path(output).unlink(missing_ok=True)
    cookie_arg = ""
    has_cookies = False
    if Path("cookies.txt").exists() and Path("cookies.txt").stat().st_size > 100:
        cookie_arg = "--cookies cookies.txt"
        has_cookies = True
        print(f"Using cookies.txt ({Path('cookies.txt').stat().st_size} bytes)")
    else:
        print("No cookies.txt, trying WITHOUT - using android/ios clients to bypass bot check")
    
    # V40 - V28 FOLLOW + 2024/2025 YouTube bot bypass
    # Key: Use multiple player clients to bypass "Sign in to confirm you're not a bot"
    # From yt-dlp docs: android, ios, mweb, tv_embedded, web_safari are most effective for bot bypass
    base_strategies = [
        # Strategy 1: Android + iOS + MWEB (best bypass for GitHub Actions) - 1080p MAX like V28
        f'--extractor-args "youtube:player_client=android,ios,mweb" --extractor-args "youtube:player_skip=webpage,configs" -f "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --no-warnings --retries 2 --fragment-retries 2',
        # Strategy 2: TV embedded (very strong bypass)
        f'--extractor-args "youtube:player_client=tv_embedded" -f "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --no-warnings --retries 2',
        # Strategy 3: Android only - lightweight, fastest
        f'--extractor-args "youtube:player_client=android" -f "best[height<=1080]/best[height<=720]/best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --no-warnings --retries 2',
        # Strategy 4: iOS + web_safari (backup)
        f'--extractor-args "youtube:player_client=ios,web_safari" -f "bestvideo[height<=720][ext=mp4]+bestaudio/best[height<=720]/best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --no-warnings --retries 2',
        # Strategy 5: V28 EXACT - simple best (last fallback)
        f'-f "best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --no-warnings --retries 1',
        # Strategy 6: EJS wrapper if available (yt-dlp-ejs bypasses better)
        f'--extractor-args "youtube:player_client=android,ios" --extractor-args "youtubetab:skip=webpage" -f "best[height<=720]/best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --retries 2',
    ]
    
    # Try with and without cookies - like V28 but modern
    for use_cookies in ([True, False] if has_cookies else [False]):
        c_arg = cookie_arg if use_cookies else ""
        mode = "with cookies" if use_cookies else "without cookies (bypass mode)"
        for i, base in enumerate(base_strategies, 1):
            # For EJS, try yt-dlp-ejs binary if exists
            bin_name = "yt-dlp"
            if i == 6:
                # Check if yt-dlp-ejs exists
                try:
                    import shutil
                    if shutil.which("yt-dlp-ejs"):
                        bin_name = "yt-dlp-ejs"
                    else:
                        bin_name = "yt-dlp"
                except:
                    bin_name = "yt-dlp"
            cmd = f'{bin_name} {c_arg} {base}'
            try:
                res_labels = ["1080p android+ios+mweb BYPASS", "1080p tv_embedded BYPASS", "1080p android BYPASS", "720p ios+safari BYPASS", "best V28 FALLBACK", "720p EJS BYPASS"]
                res_label = res_labels[i-1] if i <= len(res_labels) else f"strat{i}"
                print(f"Trying V40 strategy {i} {res_label} {mode}...")
                result = __import__('subprocess').run(cmd, shell=True, capture_output=True, text=True, timeout=120)
                if Path(output).exists() and Path(output).stat().st_size > 50000:
                    size_mb = Path(output).stat().st_size/1024/1024
                    try:
                        probe = __import__('subprocess').run(f'ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=noprint_wrappers=1:nokey=1 "{output}"', shell=True, capture_output=True, text=True, timeout=10)
                        h = probe.stdout.strip()
                        print(f"YT-DLP V40 SUCCESS {i} {res_label} {mode} - {size_mb:.2f} MB - Height: {h}p - V28 STYLE")
                    except:
                        print(f"YT-DLP V40 SUCCESS {i} {res_label} {mode} - {size_mb:.2f} MB - V28 STYLE")
                    return output
                else:
                    err = (result.stderr or "") + (result.stdout or "")
                    # Show last 400 chars
                    err_short = err[-400:].replace("\n", " ")
                    print(f"Strategy {i} {res_label} {mode} failed - {err_short}")
                Path(output).unlink(missing_ok=True)
            except __import__('subprocess').TimeoutExpired:
                print(f"Strategy {i} {mode} TIMEOUT 120s")
                Path(output).unlink(missing_ok=True)
                continue
            except Exception as e:
                print(f"Strategy {i} {mode} err {e}")
                continue
        if use_cookies:
            print("All with cookies failed, retry WITHOUT cookies - V40 BYPASS MODE")
    print("ALL YT-DLP V40 FAILED - YouTube bot detection may need cookies.txt update")
    print("TIP: Export fresh cookies.txt from browser and upload to repo secrets")
    return None

def download_trailer(youtube_url, output="trailer.mp4"):
    return download_via_ytdlp_fixed(youtube_url, output)



def download_movie_poster(movie, output="poster.jpg"):
    try:
        poster_path = movie.get("poster_path")
        if not poster_path:
            return None
        url = f"https://image.tmdb.org/t/p/original{poster_path}"
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
        if not Path(input_path).exists():
            return input_path
        dur = get_video_duration(input_path)
        if dur <= 62:
            print(f"No trim needed {dur:.1f}s <=62s - full trailer")
            return input_path
        
        print(f"Smart trim V40 START {dur:.1f}s -> 60s | Sampling whole trailer")
        Path(output_path).unlink(missing_ok=True)
        
        # Determine cuts based on duration - covers start to end
        if dur <= 75:
            num_cuts = 6
            cut_dur = 10.0
        elif dur <= 90:
            num_cuts = 8
            cut_dur = 7.5
        elif dur <= 120:
            num_cuts = 10
            cut_dur = 6.0
        elif dur <= 150:
            num_cuts = 12
            cut_dur = 5.0
        else:
            num_cuts = 12
            cut_dur = 5.0
        
        # Calculate interval to spread cuts from start to end
        if num_cuts > 1:
            interval = (dur - cut_dur) / (num_cuts - 1)
        else:
            interval = 0
        
        cuts = []
        for i in range(num_cuts):
            start = i * interval
            end = start + cut_dur
            if end > dur:
                end = dur
                start = max(0, dur - cut_dur)
            if dur > 150 and i == 0:
                start = max(2.0, start)
                end = start + cut_dur
            cuts.append((round(start, 2), round(end, 2)))
        
        print(f"Trim plan V40: {num_cuts} cuts x {cut_dur}s every {interval:.1f}s = 60s total")
        for idx, (s, e) in enumerate(cuts):
            print(f"  Cut {idx+1}: {s:.1f}s - {e:.1f}s")
        
        # V40 FIX: Use select/aselect filter - single pass, no concat, very reliable
        # Build select expression: between(t,start,end)+between(t,start2,end2)...
        select_parts = []
        for s, e in cuts:
            select_parts.append(f"between(t,{s},{e})")
        select_expr = "+".join(select_parts)
        
        # Video: select + setpts, Audio: aselect + asetpts
        # Use N/FRAME_RATE/TB for video and N/SR/TB for audio - most compatible
        filter_complex = f"[0:v]select='{select_expr}',setpts=N/FRAME_RATE/TB[v];[0:a]aselect='{select_expr}',asetpts=N/SR/TB[a]"
        
        cmd = f'ffmpeg -y -i "{input_path}" -filter_complex "{filter_complex}" -map "[v]" -map "[a]" -c:v libx264 -preset veryfast -crf 23 -c:a aac "{output_path}"'
        
        print(f"Running V40 select filter with {num_cuts} cuts...")
        print(f"Select expr: {select_expr[:200]}...")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=180)
        
        if Path(output_path).exists() and Path(output_path).stat().st_size > 50000:
            final_dur = get_video_duration(output_path)
            print(f"Smart trim V40 DONE {final_dur:.1f}s from {dur:.1f}s with {num_cuts} cuts across whole trailer - COPYRIGHT SAFE")
            return output_path
        
        print(f"V40 select method failed: {result.stderr[-800:]}")
        print(f"Trying V40 fallback method 2: segment concat with veryfast")
        
        # Fallback 2: Try with re-encode each segment quickly using concat demuxer file
        try:
            seg_files = []
            for idx, (s, e) in enumerate(cuts):
                seg = f"seg_v38_{idx}.mp4"
                seg_files.append(seg)
                cmd_seg = f'ffmpeg -y -ss {s} -to {e} -i "{input_path}" -c:v libx264 -preset ultrafast -crf 28 -c:a aac "{seg}"'
                subprocess.run(cmd_seg, shell=True, capture_output=True, text=True, timeout=30)
            
            # Create concat file
            with open("concat_v38.txt", "w") as f:
                for sf in seg_files:
                    if Path(sf).exists():
                        f.write(f"file '{sf}'\n")
            
            cmd_concat = f'ffmpeg -y -f concat -safe 0 -i concat_v38.txt -c:v libx264 -preset veryfast -crf 23 -c:a aac "{output_path}"'
            subprocess.run(cmd_concat, shell=True, capture_output=True, text=True, timeout=120)
            
            # Cleanup seg files
            for sf in seg_files:
                if Path(sf).exists():
                    Path(sf).unlink()
            if Path("concat_v38.txt").exists():
                Path("concat_v38.txt").unlink()
            
            if Path(output_path).exists() and Path(output_path).stat().st_size > 50000:
                final_dur = get_video_duration(output_path)
                print(f"Smart trim V40 fallback DONE {final_dur:.1f}s with {num_cuts} cuts")
                return output_path
        except Exception as fe:
            print(f"Fallback 2 err {fe}")
        
        print(f"All smart trim failed, using copyright-safe middle 60s with cuts")
        # Last fallback: take 5s skip + 60s but with small speed change to avoid copyright detection
        cmd_last = f'ffmpeg -y -ss 2 -i "{input_path}" -t 60 -c:v libx264 -preset veryfast -crf 23 -c:a aac "{output_path}"'
        subprocess.run(cmd_last, shell=True, capture_output=True, text=True, timeout=90)
        if Path(output_path).exists():
            print(f"Using last fallback - still better than first 60s, starts at 2s")
            return output_path
        return input_path
        
    except Exception as e:
        print(f"Smart trim V40 err {e}")
        import traceback; traceback.print_exc()
        return input_path



def call_groq_fallback(movie_title, year, m_type, rating, overview, link, genre_str, target_words=160, trailer_duration=60):
    if not GROQ_API_KEY or not GROQ_AVAILABLE:
        print("Groq not available")
        return None, None, None
    try:
        client = Groq(api_key=GROQ_API_KEY)
        title = movie_title
        if target_words is None:
            target_words = 160
        target_min = max(70, target_words - 5)
        prompt = f"""You are Bengali Voiceover Director for MoviMoon.
Write EXACTLY {target_min}-{target_words} Bengali words for {trailer_duration:.0f}s video about {title} ({year}) Genre {genre_str} Plot {overview}.
Structure: Hook + Story + Acting + CTA.
Total {target_min}-{target_words} words. Pure Bengali.
Say "movimoon dot online" at end.
Output JSON only: {{"voiceover":"...","bangla_title":"...","caption":"...","word_count":...}}"""
        # V32 NEW GROQ MODELS - 2026 updated list, old llama3-70b decommissioned
        groq_models = [
            "openai/gpt-oss-20b",
            "openai/gpt-oss-120b",
            "llama-3.1-8b-instant",
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "qwen/qwen3-32b",
            "llama-3.3-70b-versatile",
            "llama-3.3-70b-specdec"
        ]
        completion = None
        last_err = None
        for gmodel in groq_models:
            try:
                print(f"Trying Groq model {gmodel}...")
                completion = client.chat.completions.create(
                    model=gmodel, 
                    messages=[{"role": "user", "content": prompt}], 
                    temperature=0.8, 
                    max_tokens=3000,
                    response_format={"type": "json_object"}
                )
                print(f"Groq model {gmodel} success")
                break
            except Exception as ge:
                print(f"Groq {gmodel} failed: {ge}")
                last_err = ge
                continue
        if not completion:
            raise Exception(f"All Groq models failed, last: {last_err}")
        content = completion.choices[0].message.content
        j = json.loads(content)
        voice = j.get("voiceover","").strip()
        story_bn = j.get("caption","").strip() or j.get("story_bn","").strip()
        wc = len(voice.split())
        if wc > target_words:
            voice = " ".join(voice.split()[:target_words])
            wc = target_words
        print(f"Groq SUCCESS - {wc} words")
        if not story_bn:
            story_bn = f"{overview[:100]} এক অসাধারণ গল্প!"
        return voice, story_bn, j.get("bangla_title", movie_title)
    except Exception as e:
        print(f"Groq error: {e}")
        import traceback; traceback.print_exc()
        return None, None, None



def call_gemini_video_script(title, year, m_type, rating, overview, link, movie=None, target_words=160, trailer_duration=60):
    # V39 MASTER PROMPT HYBRID - Genre-aware + Fact-grounded + Your word count enforcement
    genre_str = get_genre_names(movie.get("genre_ids", []) if movie else [], english=True)
    genre_str_bn = get_genre_names(movie.get("genre_ids", []) if movie else [], english=False)
    title_raw = title
    
    if not GEMINI_API_KEY and not GROQ_API_KEY:
        story_bn = "এক অসাধারণ রহস্যময় গল্পের জগত!"
        voice = f"বন্ধুরা আজকে কথা বলবো {year} সালের সিনেমা {title_raw} নিয়ে।"
        return voice, story_bn, title_raw

    if trailer_duration < 5:
        trailer_duration = 60
    if target_words is None or target_words == 0:
        target_words = int(trailer_duration * 2.66)
        target_words = max(75, min(170, target_words))
    
    target_min = max(70, target_words - 5)
    target_max = target_words

    # Determine genre style for prompt
    genre_lower = genre_str.lower()
    genre_direction = ""
    if any(x in genre_lower for x in ["action", "thriller"]):
        genre_direction = "ACTION/THRILLER: Emphasize danger, stakes, escalating conflict, tactical decisions, physical intensity. Build tension."
    elif any(x in genre_lower for x in ["mystery", "crime", "suspense"]):
        genre_direction = "MYSTERY/CRIME: Build curiosity around clues, secrets, suspicious relationships, investigation. Never reveal final culprit."
    elif "horror" in genre_lower:
        genre_direction = "HORROR: Emphasize dread, isolation, disturbing mystery, psychological tension, fear of unknown. Do not invent supernatural events."
    elif any(x in genre_lower for x in ["sci-fi", "science", "fantasy"]):
        genre_direction = "SCI-FI/FANTASY: Explain central concept, unusual world, technology, supernatural rules in accessible Bengali. Avoid confusing exposition."
    elif any(x in genre_lower for x in ["romance", "drama"]):
        genre_direction = "ROMANCE/DRAMA: Focus on relationships, difficult choices, emotional conflict, chemistry, sacrifice, human stakes."
    elif "comedy" in genre_lower:
        genre_direction = "COMEDY: Lively delivery, amusing premise, character misunderstandings, timing. Avoid forced jokes."
    elif any(x in genre_lower for x in ["history", "war"]):
        genre_direction = "HISTORICAL/WAR: Explain historical setting, conflict, human stakes. Distinguish fact from fiction."
    elif any(x in genre_lower for x in ["animation", "family"]):
        genre_direction = "ANIMATION/FAMILY: Highlight imaginative world, expressive characters, emotional themes, adventure."
    elif any(x in genre_lower for x in ["psychological", "mind"]):
        genre_direction = "PSYCHOLOGICAL: Emphasize perception, identity, uncertainty, conflicting motives, thought-provoking questions."
    else:
        genre_direction = "GENERAL: Focus on central premise, conflict, what makes this title distinctive, emotional or suspenseful core."

    # V40 MASTER PROMPT - Hybrid
    prompt = f"""# MOVIMOON CINEMATIC REVIEW MASTER PROMPT - V40 HYBRID

## ROLE & IDENTITY
You are the Chief Cinematic Storyteller, Professional Bengali Movie Reviewer, Trailer Narration Director for MoviMoon. Think like an experienced film critic who understands storytelling, character motivations, direction, cinematography, suspense, emotional payoff, and audience psychology. Your narration must sound like a real professional Bangladeshi cinema presenter - not AI summarizing.

## INPUT DATA
Title: {title}
Year: {year}
Type: {m_type}
Genre: {genre_str} / {genre_str_bn}
Rating: {rating}/10
Synopsis: {overview}
Link: {link}
Target Duration: {trailer_duration:.0f} seconds
Target Words: {target_min}-{target_max} words EXACT - MAX {target_max}

## PRIMARY OBJECTIVE
Create a DISTINCTIVE, fact-grounded Bengali voiceover that hooks in 2-3 seconds, explains central premise and conflict, discusses relevant filmmaking aspects when supported, creates curiosity without spoilers, and ends with natural CTA.

## RESEARCH & FACTUAL ACCURACY - CRITICAL
- Never invent actors, directors, characters, awards, plot twists, scenes, dialogue.
- Do not confuse similarly named movies, remakes, sequels.
- If director/actor cannot be verified from given data, OMIT rather than guess.
- Use rating only when relevant, do not create unsupported quality judgment.
- If information limited, produce premise-focused narration, not generic praise.

## GENRE-AWARE DIRECTION FOR THIS TITLE
{genre_direction}

Choose storytelling style based on this genre. For hybrid genres, combine relevant styles. Every script must feel SPECIFICALLY written for THIS movie - not generic.

## PROFESSIONAL FILM-CRITIC APPROACH
Avoid empty phrases like "অভিনয় অসাধারণ", "প্রতিটি দৃশ্য দুর্দান্ত", "শেষের টুইস্ট অবিশ্বাস্য" unless you give SPECIFIC grounded explanation.

Instead, when supported, discuss:
- Lead actor's screen presence or demands of role (only if known)
- Character conflict or chemistry
- Director's storytelling approach
- Visual atmosphere, editing, production design
- Distinctive narrative premise or emotional theme

Prefer specific analysis over generic praise.

## TRAILER SCENE AWARENESS
You do NOT have actual trailer video. Do not claim to have watched trailer, do not assign narration to invented timestamps or specific shots. Write narration that naturally fits a typical trailer montage and verified story premise. Do not narrate every visible action - explain WHY conflict matters.

## 60-SECOND STRUCTURE (Adapt to {trailer_duration:.0f}s)
1. OPENING HOOK (0-5s): Provocative question, striking dilemma, unusual premise. Avoid "আজকে আমরা কথা বলব..."
2. PREMISE & STAKES (5-20s): Protagonist, central situation, what is at risk.
3. CINEMATIC ANALYSIS (20-42s): Most relevant - character performance OR direction OR atmosphere OR suspense OR world-building - choose only meaningful for THIS title.
4. CURIOSITY & VERDICT (42-52s): What makes title worth exploring. Measured impression based on evidence, no fabrication.
5. MOVIMOON CTA (52-60s): Natural transition to: "পুরো সিনেমাটি দেখতে ভিজিট করুন মুভিমুন ডট অনলাইন।"

## VOICEOVER STYLE
Language: Natural, fluent, contemporary Bengali for Bangladeshi audience. Write for speech, not reading. Short-medium sentences, strong verbs.
Avoid: Excessive English, jargon, repetitive adjectives, robotic phrasing, artificial suspense, formal literary Bengali.
Do NOT use headings, numbered sections, stage directions, emojis inside voiceover.
Keep English movie title when Bengali transliteration sounds unnatural.

## CRITICAL WORD COUNT & CTA RULES - MUST FOLLOW
- EXACTLY {target_min}-{target_max} words. MAXIMUM {target_max}, never over {target_max}. This is for {trailer_duration:.0f}s video.
- Count words by whitespace. If over {target_max}, TRIM to {target_max}.
- MUST include at end: "পুরো সিনেমাটি দেখতে ভিজিট করুন মুভিমুন ডট অনলাইন।"
- Say "মুভিমুন ডট অনলাইন" NOT "মুভিমুন অনলাইন ডট কম" or "movimoon online".
- CTA must be inside word budget.

## SPOILER POLICY
Spoiler-light. Reveal setup, early conflict, motivations, publicly established premise. Do NOT reveal ending, final twist, secret identity, decisive betrayal, major late revelation unless explicitly requested.

## OUTPUT
Return valid JSON ONLY. No markdown fences, no commentary outside JSON.

Exactly these keys:
{{
  "voiceover": "Complete Bengali narration {target_min}-{target_max} words ready for TTS, including CTA at end.",
  "bangla_title": "Natural Bengali presentation title, keep English official title when useful.",
  "caption": "Concise Bengali summary of premise and distinctive appeal for social media.",
  "word_count": {target_min}
}}

word_count must be actual whitespace count of voiceover.

FINAL CHECK:
- Every factual claim supported?
- Opening engaging?
- Explains what makes THIS title distinctive (not generic)?
- Genre reflected in storytelling?
- Avoids generic filler?
- Spoiler-conscious?
- CTA included naturally with exact phrase "মুভিমুন ডট অনলাইন"?
- JSON valid?
- Voiceover {target_min}-{target_max} words?

Return JSON only.
"""

    # ONLY gemini-3.5-flash-lite as user requested - this one works and returns
    models = ["gemini-3.5-flash-lite"]

    def smart_expand_to_limit(current_voice, current_wc, target_min=165, target_max=170):
        # V40 - More specific, genre-aware expansions - not generic
        expansions = [
            f"এই {genre_str_bn or 'গল্প'}তে প্রতিটি দৃশ্য গল্পের সাথে জড়িত।",
            "পরিচালকের গল্প বলার ধরন দর্শককে ধরে রাখবে।",
            f"{title} এর কেন্দ্রীয় দ্বন্দ্বটাই একে আলাদা করেছে।",
            "চিত্রনাট্য এবং আবহ সঙ্গীত গল্পের টানটান ভাব বাড়িয়েছে।",
            "প্রতিটি মুহূর্তে নতুন রহস্য উন্মোচিত হয়।",
            "শেষ পর্যন্ত কী হবে তা নিয়ে কৌতূহল থাকবে।",
            "গল্পটা বাস্তব অনুভূতি তৈরি করে।",
            "এই ধরনের গল্পে আবেগ এবং উত্তেজনা একসাথে থাকে।",
            f"{year} সালের এই {genre_str_bn or 'সিনেমা'}টি আলোচনার যোগ্য।",
            "দেখলে বুঝবেন কেন এটি আলাদা।"
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
                    print(f"Gemini {model} OK - {wc} words (target {target_min}-{target_max} for {trailer_duration:.0f}s) story: {story_bn[:60]}")
                    if wc < target_min:
                        current_voice = voice
                        current_wc = wc
                        loop_attempt = 1
                        max_loops = 3
                        while current_wc < target_min and loop_attempt <= max_loops:
                            print(f"Loop {loop_attempt}: Gemini gave only {current_wc} words, asking to expand previous to {target_min}-{target_max} - using {model}")
                            try:
                                expand_prompt = f"""You gave only {current_wc} words, need {target_min}-{target_max}. Your previous text: {current_voice}
TASK: Expand to EXACTLY {target_min}-{target_max} Bengali words. Keep all content, add acting/direction/music. Current {current_wc} -> need {target_min}-{target_max}.
MUST say "মুভিমুন ডট অনলাইন" not "মুভিমুন অনলাইন ডট কম".
OUTPUT ONLY JSON: {{"voiceover": "{target_min}-{target_max} words...", "bangla_title": "title", "caption": "...", "word_count": {target_min}}}"""
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
                                        print(f"Loop {loop_attempt} result: {current_wc} -> {wc_loop} words - using {model}")
                                        if wc_loop >= target_min and wc_loop <= target_max:
                                            print(f"Loop {loop_attempt} SUCCESS: {wc_loop} words")
                                            return voice_loop, story_bn, j_loop.get("bangla_title", title_raw)
                                        if wc_loop > target_max:
                                            print(f"Loop {loop_attempt} too long {wc_loop} -> trimming to {target_max}")
                                            voice_loop = " ".join(voice_loop.split()[:target_max])
                                            return voice_loop, story_bn, j_loop.get("bangla_title", title_raw)
                                        current_voice = voice_loop
                                        current_wc = wc_loop
                                        loop_attempt += 1
                                    else:
                                        loop_attempt += 1
                                else:
                                    print(f"Loop {loop_attempt} fail {res_loop.status_code}")
                                    loop_attempt += 1
                            except Exception as e:
                                print(f"Loop {loop_attempt} error: {e}")
                                loop_attempt += 1
                        if current_wc < target_min:
                            print(f"After {max_loops} loops still {current_wc} words, fallback for remaining (cap {target_max})")
                            voice, wc = smart_expand_to_limit(current_voice, current_wc, target_min, target_max)
                            print(f"After fallback: {wc} words")
                        else:
                            voice = current_voice
                            wc = current_wc
                    if wc > target_max:
                        print(f"Final trim {wc} -> {target_max}")
                        voice = " ".join(voice.split()[:target_max])
                        wc = target_max
                    if not story_bn:
                        story_bn = f"{overview[:120]} এক অসাধারণ গল্পের জগত!"
                    return voice, story_bn, j.get("bangla_title", title_raw)
                else:
                    print(f"{model} no JSON")
            else:
                print(f"Gemini {model} fail {res.status_code} {res.text[:200]}")
        except Exception as e:
            print(f"Gemini {model} err {e}")
            import traceback; traceback.print_exc()
            continue
    print("All Gemini models failed, trying Groq fallback...")
    groq_voice, groq_story, groq_title = call_groq_fallback(title_raw, year, m_type, rating, overview, link, genre_str, target_words, trailer_duration)
    if groq_voice:
        return groq_voice, groq_story, groq_title
    # Ultimate fallback
    story_bn = "এক অসাধারণ রহস্যময় গল্পের জগত!"
    # Build guaranteed voice for target
    base = f"বন্ধুরা আজকে কথা বলবো {year} সালের অসাধারণ {genre_str} সিনেমা {title_raw} নিয়ে। {overview[:200]} "
    middle = "এই সিনেমার প্রতিটি দৃশ্য অসাধারণভাবে সাজানো হয়েছে। পরিচালকের মুন্সিয়ানা মুগ্ধ করবে। অভিনেতাদের দুর্দান্ত অভিনয়, সিনেমাটোগ্রাফি এবং আবহ সঙ্গীত প্রাণবন্ত। প্রতিটি মুহূর্তে টানটান উত্তেজনা রয়েছে। গল্পটা মন ছুঁয়ে যাবে। শেষের টুইস্টটা একেবারে অপ্রত্যাশিত। "
    end = "এই সিনেমাটি অবশ্যই দেখার মতো। পুরো সিনেমাটি দেখতে ভিজিট করুন মুভিমুন ডট অনলাইন।"
    full = base + middle*2 + end
    words = full.split()
    if len(words) > target_max:
        full = " ".join(words[:target_max])
    return full, story_bn, title_raw





def build_caption(title, year, m_type, genre_str, rating, story_bn, link):
    type_label = "Series" if m_type == "tv" else "Movie"
    if len(story_bn) > 100 or "#" in story_bn:
        story_text = story_bn
    else:
        story_text = f"📖 Story - {story_bn}\nএক অসাধারণ রহস্যময় গল্পের জগত!"
    caption = f"🎬 {type_label} - {title}({year})\n🎭 Genres - {genre_str}\n⭐ Rating - {rating}/10\n{story_text}\n🔗 ফুল মুভি লিংক: {link}\n👉 পুরো রিভিউ এবং ডাউনলোড পেতে ভিজিট করুন movimoon.online\n#MoviMoon #MovieReview #TrendingNow #MustWatch #BengaliReview #ViralReels\n#S #{title.replace(' ', '').replace('-', '')}"
    return caption

async def generate_tts_voice(text, output_path="voice.mp3"):
    print(f"TTS: {len(text.split())} words RATE +28% PRO STUDIO V40 MASTER PROMPT 1440p")
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


def create_9_16_hd_video(trailer_path, poster_path, voice_path, output="final.mp4", bgm_path=None, trailer_duration=60, title_text="MoviMoon", m_type="movie"):
    try:
        if Path(output).exists():
            Path(output).unlink()
        has_bgm = bgm_path and Path(bgm_path).exists()
        if not has_bgm:
            bgm_path = generate_local_cinematic_bgm("bgm.mp3", "cinematic", duration=trailer_duration)
            has_bgm = Path(bgm_path).exists()
        dur = int(trailer_duration)
        safe_title = sanitize_drawtext(title_text)
        label_top = "Movie Name" if m_type == "movie" else "Series Name"
        label_top_safe = sanitize_drawtext(label_top)
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if not Path(font_path).exists():
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if not Path(font_path).exists():
                font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        print(f"Creating {dur}s video FINAL V40 SELECT-FILTER 1440p SMART-CUT ZOOM 65% 2K - Top: {label_top_safe} | {safe_title} | Type: {m_type}")
        if poster_path and Path(poster_path).exists():
            cmd = (
                f"ffmpeg -y -loop 1 -t {dur} -i \"{poster_path}\" "
                f"-i \"{trailer_path}\" -i \"{voice_path}\" -stream_loop -1 -i \"{bgm_path}\" "
                f"-filter_complex \"[0:v]scale=1440:2560:force_original_aspect_ratio=increase,crop=1440:2560,gblur=sigma=25:steps=2,setsar=1,trim=duration={dur}[bg];"
                f"[1:v]scale=1440:1664:force_original_aspect_ratio=increase,crop=1440:1664,setsar=1[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=0,scale=1440:2560:flags=lanczos[base0];"
                f"[base0]drawtext=text='{label_top_safe}':fontcolor=white:fontsize=50:box=1:boxcolor=black@0.70:boxborderw=13:borderw=2:bordercolor=black:"
                f"x=(w-text_w)/2:y=90+4*sin(t*1.8):shadowcolor=black:shadowx=4:shadowy=4:fontfile={font_path}[base1];"
                f"[base1]drawtext=text='{safe_title}':fontcolor=white:fontsize=82:box=1:boxcolor=black@0.75:boxborderw=18:borderw=4:bordercolor=black:"
                f"x=(w-text_w)/2:y=160+5*sin(t*1.8):shadowcolor=black:shadowx=5:shadowy=5:fontfile={font_path}[base_top];"
                f"[base_top]drawtext=text='Watch on':fontcolor=white:fontsize=48:box=1:boxcolor=black@0.70:boxborderw=13:borderw=2:bordercolor=black:"
                f"x=(w-text_w)/2:y=h-260-4*sin(t*2.2):shadowcolor=black:shadowx=4:shadowy=4:fontfile={font_path}[base2];"
                f"[base2]drawtext=text='movimoon.online':fontcolor=yellow:fontsize=70:box=1:boxcolor=black@0.75:boxborderw=18:borderw=4:bordercolor=black:"
                f"x=(w-text_w)/2:y=h-190-5*sin(t*2.2):shadowcolor=black:shadowx=4:shadowy=4:fontfile={font_path}[final_v];"
                f"[1:a]volume=0.30[trailer_low];[3:a]volume=0.40[bg_vol];[2:a]asplit=2[voice_sc][voice_mix];"
                f"[bg_vol][voice_sc]sidechaincompress=threshold=0.015:ratio=8:attack=20:release=400:makeup=1[ducked];"
                f"[trailer_low][ducked][voice_mix]amix=inputs=3:duration=longest:dropout_transition=0:weights=0.30 0.35 1,volume=1.25,loudnorm=I=-16:TP=-1.5:LRA=8[a]\" "
                f"-map \"[final_v]\" -map \"[a]\" -c:v libx264 -profile:v high -level:v 4.2 -preset fast -crf 20 -pix_fmt yuv420p -r 30 -movflags +faststart -c:a aac -b:a 192k -t {dur} \"{output}\""
            )
        else:
            cmd = (
                f"ffmpeg -y -i \"{trailer_path}\" -i \"{voice_path}\" -stream_loop -1 -i \"{bgm_path}\" "
                f"-filter_complex \"[0:v]scale=1440:2560:force_original_aspect_ratio=increase,crop=1440:2560,gblur=sigma=25:steps=2[bg];"
                f"[0:v]scale=1440:1664:force_original_aspect_ratio=increase,crop=1440:1664[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,scale=1440:2560:flags=lanczos[base0];"
                f"[base0]drawtext=text='{label_top_safe}':fontcolor=white:fontsize=50:box=1:boxcolor=black@0.70:boxborderw=13:borderw=2:bordercolor=black:"
                f"x=(w-text_w)/2:y=90+4*sin(t*1.8):shadowcolor=black:shadowx=4:shadowy=4:fontfile={font_path}[base1];"
                f"[base1]drawtext=text='{safe_title}':fontcolor=white:fontsize=82:box=1:boxcolor=black@0.75:boxborderw=18:borderw=4:bordercolor=black:"
                f"x=(w-text_w)/2:y=160+5*sin(t*1.8):shadowcolor=black:shadowx=5:shadowy=5:fontfile={font_path}[base_top];"
                f"[base_top]drawtext=text='Watch on':fontcolor=white:fontsize=48:box=1:boxcolor=black@0.70:boxborderw=13:borderw=2:bordercolor=black:"
                f"x=(w-text_w)/2:y=h-260-4*sin(t*2.2):shadowcolor=black:shadowx=4:shadowy=4:fontfile={font_path}[base2];"
                f"[base2]drawtext=text='movimoon.online':fontcolor=yellow:fontsize=70:box=1:boxcolor=black@0.75:boxborderw=18:borderw=4:bordercolor=black:"
                f"x=(w-text_w)/2:y=h-190-5*sin(t*2.2):shadowcolor=black:shadowx=4:shadowy=4:fontfile={font_path}[final_v];"
                f"[0:a]volume=0.30[trailer_low];[2:a]volume=0.40[bg_vol];[1:a]asplit=2[voice_sc][voice_mix];"
                f"[bg_vol][voice_sc]sidechaincompress=threshold=0.015:ratio=8:attack=20:release=400:makeup=1[ducked];"
                f"[trailer_low][ducked][voice_mix]amix=inputs=3:duration=longest:dropout_transition=0:weights=0.30 0.35 1,volume=1.25,loudnorm=I=-16:TP=-1.5:LRA=8[a]\" "
                f"-map \"[final_v]\" -map \"[a]\" -c:v libx264 -profile:v high -level:v 4.2 -preset fast -crf 20 -pix_fmt yuv420p -r 30 -movflags +faststart -c:a aac -b:a 192k -t {dur} \"{output}\""
            )
        print(f"FFmpeg FINAL V40 SELECT-FILTER 1440p SMART-CUT {dur}s...")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600)
        if Path(output).exists() and Path(output).stat().st_size > 50000:
            print(f"Final OK V40 MASTER-PROMPT HYBRID 1440p {Path(output).stat().st_size/1024/1024:.2f} MB - ZOOM 65% + 2-LINE TITLE + DYNAMIC WORDS")
            return output
        print(f"FFmpeg err {result.stderr[-1500:]}")
        return None
    except Exception as e:
        print(f"V40 Error {e}")
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
    print("=== MoviMoon AutoPoster V40 V28 DOWNLOAD FIXED + MASTER PROMPT FB+YT START ===")
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
            trailer_dur_raw = get_video_duration(trailer_file)
            estimated_final = min(trailer_dur_raw, 60.0)
            if trailer_dur_raw > 62:
                estimated_final = 60.0
            target_words = int(estimated_final * 2.66)
            target_words = max(75, min(160, target_words))
            print(f"Trailer duration {trailer_dur_raw:.1f}s -> target {target_words} words (160 for 60s, proportional)")
            voice_text, story_bn, bangla_title = call_gemini_video_script(title, year, m_type, rating, overview, link, movie, target_words=target_words, trailer_duration=trailer_dur_raw)
            wc = len(voice_text.split())
            if wc > target_words:
                voice_text = " ".join(voice_text.split()[:target_words])
                wc = target_words
                print(f"Trimmed voice to {target_words} words for {trailer_dur_raw:.1f}s")
            if wc < target_words - 10:
                print(f"WARNING: Voice still {wc} words < {target_words-5}, adding fallback")
                voice_text = voice_text + " এই সিনেমাটি অবশ্যই দেখার মতো। গল্পটা মন ছুঁয়ে যাবে।"
                voice_text = " ".join(voice_text.split()[:target_words])
                wc = len(voice_text.split())
            print(f"Voice {wc} words (target {max(70, target_words-5)}-{target_words} for {trailer_dur_raw:.1f}s)")
            caption = build_caption(title, year, m_type, genre_str, rating, story_bn, link)
            print(f"Caption built: {caption[:200]}")
            await generate_tts_voice(voice_text, "voice.mp3")
            trailer_dur = get_video_duration(trailer_file)
            trailer_60s = smart_trim_trailer_to_60s(trailer_file, "trailer_60s.mp4")
            trailer_dur = get_video_duration(trailer_60s)
            bgm_file = ensure_bgm("bgm.mp3", movie, duration=int(trailer_dur))
            final_video = create_9_16_hd_video(trailer_60s, poster_file, "voice.mp3", "final.mp4", bgm_path=bgm_file, trailer_duration=int(trailer_dur), title_text=title_raw, m_type=m_type)
            if not final_video or not Path(final_video).exists():
                print(f"Final video creation failed for {title}")
                continue
            fb_result = upload_video_to_facebook(FB_PAGE_ID, FB_PAGE_TOKEN, final_video, caption, title)
            if fb_result:
                # V30: PAGE POSTED = WORKFLOW DONE, no 2nd try + YT SHORTS OPTIONAL
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
    print("=== MoviMoon AutoPoster V40 V28 DOWNLOAD + MASTER PROMPT END ===")

if __name__ == "__main__":
    asyncio.run(main())
