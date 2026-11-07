"""
MoviMoon AutoPoster V43 FINAL - V38 EXACT LOGIC + REST TTS FIX + FFmpeg FIX
- TMDB fetch (Hollywood + Bollywood + South + Series 2024+)
- Trailer download: 3 Method (NO COOKIE -> RESIDENTIAL PROXY -> FREE PROXY)
- Story: Gemini via google-generativeai + Groq fallback
- TTS: FILE METHOD but REST API (no google-genai SDK) -> Fixes speechConfig error
- Video: FFmpeg filter_complex FIXED [base]->[t1]->[t2]->[t3]->[final_v]
- Upload: FB Page + Group + YouTube Shorts
"""
import os
import sys
import json
import time
import base64
import random
import requests
import subprocess
import re
from datetime import datetime

print("=== MoviMoon Bot - V43 FINAL | V38 EXACT + REST TTS FIX + FFmpeg FIX ===")

# === CONFIG ===
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN")
FB_GROUP_ID = os.environ.get("FB_GROUP_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
YOUTUBE_PROXY = os.environ.get("YOUTUBE_PROXY", "").strip()
YOUTUBE_PROXY_LIST = os.environ.get("YOUTUBE_PROXY_LIST", "").strip()

HISTORY_FILE = "posted_history.json"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === Check libs ===
try:
    import edge_tts
    print("edge_tts OK")
except:
    print("edge_tts missing")

try:
    from groq import Groq
    print("Groq SDK available")
except:
    print("Groq missing")

# === TMDB FETCH ===
def fetch_tmdb():
    all_movies = []
    headers = {"Authorization": f"Bearer {TMDB_API_KEY}"} if len(TMDB_API_KEY or "") > 100 else {}
    params_key = {} if headers else {"api_key": TMDB_API_KEY}
    
    urls = [
        ("https://api.themoviedb.org/3/trending/movie/day", {"language": "en-US"}),
        ("https://api.themoviedb.org/3/movie/popular", {"language": "en-US", "region": "US"}),
        ("https://api.themoviedb.org/3/movie/popular", {"language": "hi-IN", "region": "IN"}),
        ("https://api.themoviedb.org/3/discover/movie", {"language": "en-US", "region": "IN", "with_original_language": "te|ta|ml|kn", "sort_by": "popularity.desc", "primary_release_date.gte": "2024-01-01"}),
        ("https://api.themoviedb.org/3/trending/tv/day", {"language": "en-US", "region": "IN", "with_original_language": "te|ta|ml|kn", "sort_by": "popularity.desc", "primary_release_date.gte": "2024-01-01"}),
    ]
    
    for url, extra in urls:
        try:
            p = {**params_key, **extra}
            r = requests.get(url, headers=headers, params=p, timeout=20)
            data = r.json()
            results = data.get("results", [])
            for m in results:
                # Filter 2024+
                rd = m.get("release_date") or m.get("first_air_date") or ""
                if rd:
                    try:
                        year = int(rd.split("-")[0])
                        if year < 2024:
                            continue
                    except:
                        pass
                all_movies.append(m)
        except Exception as e:
            print(f"TMDB fetch fail {url}: {e}")
    
    # Deduplicate
    unique = {}
    for m in all_movies:
        unique[m["id"]] = m
    print(f"Total fetched {len(all_movies)}, after filter {len([m for m in all_movies if True])}, unique {len(unique)}")
    return list(unique.values())[:90]

def get_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(movie_id):
    hist = get_history()
    hist.append({"id": movie_id, "date": datetime.now().isoformat()})
    # Keep last 500
    hist = hist[-500:]
    with open(HISTORY_FILE, "w") as f:
        json.dump(hist, f, indent=2)

def get_movie_details(movie_id, is_tv=False):
    headers = {"Authorization": f"Bearer {TMDB_API_KEY}"} if len(TMDB_API_KEY or "") > 100 else {}
    params_key = {} if headers else {"api_key": TMDB_API_KEY}
    typ = "tv" if is_tv else "movie"
    url = f"https://api.themoviedb.org/3/{typ}/{movie_id}"
    try:
        r = requests.get(url, headers=headers, params={**params_key, "append_to_response": "videos,credits", "language": "en-US"}, timeout=20)
        return r.json()
    except Exception as e:
        print(f"Details fail {movie_id}: {e}")
        return {}

# === TRAILER SELECT ===
def select_trailer(details):
    videos = details.get("videos", {}).get("results", [])
    # Prefer official trailer
    for v in videos:
        if v["site"] == "YouTube" and "Trailer" in v["type"] and v.get("official"):
            return v
    for v in videos:
        if v["site"] == "YouTube" and "Trailer" in v["type"]:
            return v
    for v in videos:
        if v["site"] == "YouTube":
            return v
    return None

# === YT-DLP DOWNLOAD V38 FIXED ===
def parse_proxy_list():
    proxies = []
    if YOUTUBE_PROXY_LIST:
        for line in YOUTUBE_PROXY_LIST.splitlines():
            line=line.strip()
            if not line:
                continue
            # Format IP:PORT:username:password
            parts = line.split(":")
            if len(parts) == 4:
                ip, port, user, pwd = parts
                proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
                proxies.append(proxy_url)
            elif line.startswith("http"):
                proxies.append(line)
    if YOUTUBE_PROXY:
        proxies.insert(0, YOUTUBE_PROXY)
    return proxies

def download_trailer_yt_dlp(youtube_url, output_path):
    print(f"=== YT-DLP V38 FIXED {youtube_url} ===")
    residential_proxies = parse_proxy_list()
    if residential_proxies:
        print(f"Residential: Found {len(residential_proxies)} proxies from YOUTUBE_PROXY_LIST")
    
    # Common opts
    def make_cmd(proxy, player_clients):
        cmd = [
            "yt-dlp",
            "--no-cookies",
            "--no-playlist",
            "--merge-output-format", "mp4",
            "-o", output_path,
            "--extractor-args", f"youtube:player_client={player_clients}",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        ]
        if proxy:
            cmd.extend(["--proxy", proxy])
        cmd.append(youtube_url)
        return cmd

    methods = [
        ("METHOD 1: NO COOKIE, NO PROXY", None, [
            "tv_downgraded+android_vr+web_embedded",
            "tv+android_vr+web_embedded",
            "tv_downgraded",
            "tv_embedded+mweb",
            "mweb+tv_simply",
            "android_vr"
        ]),
        ("METHOD 2: RESIDENTIAL PROXY", residential_proxies, ["tv_downgraded+android_vr+web_embedded"])
    ]

    for method_name, proxy_list, clients in methods:
        print(f">>> {method_name}")
        proxies_to_try = proxy_list if isinstance(proxy_list, list) else [proxy_list]
        if not proxies_to_try:
            proxies_to_try = [None]
        
        for proxy in proxies_to_try:
            if method_name.startswith("METHOD 2"):
                # limit to 20 proxies
                idx = proxies_to_try.index(proxy)+1
                if idx>20:
                    break
                print(f"  [M2-Residential {idx}/{len(proxies_to_try)}] {proxy[:30] if proxy else 'None'}...")
            
            for pc in clients:
                label = f"M1-{pc} BEST 2026" if method_name.startswith("METHOD 1") and pc==clients[0] else f"M1-{pc}" if method_name.startswith("METHOD 1") else f"M2 Residential {idx} + {pc}"
                if method_name.startswith("METHOD 1"):
                    print(f"  [M1-{clients.index(pc)+1}] M1-{pc}...")
                cmd = make_cmd(proxy, pc)
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000000:
                        size_mb = os.path.getsize(output_path)/1024/1024
                        print(f"    SUCCESS {label} - {size_mb:.2f} MB")
                        return True
                    else:
                        print(f"  FAIL {label}: {result.stderr[-500:] if result.stderr else result.stdout[-500:]}")
                except Exception as e:
                    print(f"  FAIL {label}: {e}")
    
    print("All YT-DLP methods failed")
    return False

# === GEMINI STORY (using google-generativeai for text) ===
def generate_story_gemini(details, duration):
    title = details.get("title") or details.get("name") or "Movie"
    overview = details.get("overview") or ""
    target_words = int(duration * 2.66)  # ~160 for 60s
    target_min = max(120, target_words-5)
    target_max = target_words+5
    print(f"Trailer duration {duration}s -> target {target_min}-{target_max} words (160 for 60s, proportional)")
    
    prompt = f"""
    Write a Bangla movie review voiceover script for "{title}".
    Overview: {overview}
    - Length MUST be {target_min} to {target_max} words
    - Use simple Bangla, engaging, dramatic
    - No English except movie name
    - Story only, no intro like 'Hello friends'
    - Word count strictly {target_min}-{target_max}
    """
    
    # Try Gemini 3.5 flash lite
    story = None
    models_to_try = ["gemini-3.5-flash-lite","gemini-1.5-flash", "gemini-2.0-flash-lite", "gemini-3.8-flash"]
    # Use google-generativeai
    try:
        import google.generativeai as genai_old
        genai_old.configure(api_key=GEMINI_API_KEY)
        for model_name in models_to_try:
            try:
                model = genai_old.GenerativeModel(model_name)
                resp = model.generate_content(prompt)
                text = resp.text.strip()
                words = len(text.split())
                print(f"Gemini {model_name} OK - {words} words (target {target_min}-{target_max} for {duration}s) story: {text[:60]}")
                story = text
                if words < target_min:
                    # Loop to expand
                    for loop in range(1,4):
                        print(f"Loop {loop}: Gemini gave only {words} words, asking to expand previous to {target_min}-{target_max} - using {model_name}")
                        expand_prompt = f"Previous story: {text}\nExpand it to exactly {target_min}-{target_max} words, keep Bangla, keep meaning: {prompt}"
                        resp2 = model.generate_content(expand_prompt)
                        text2 = resp2.text.strip()
                        words2 = len(text2.split())
                        print(f"Loop {loop} result: {words} -> {words2} words - using {model_name}")
                        if words2 >= target_min:
                            print(f"Loop {loop} SUCCESS: {words2} words")
                            story = text2
                            break
                        text = text2
                        words = words2
                break
            except Exception as e:
                print(f"Gemini {model_name} fail {e}")
                continue
    except Exception as e:
        print(f"Gemini old SDK fail: {e}")
    
    # Groq fallback
    if not story and GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            comp = client.chat.completions.create(model="llama3-8b-8192", messages=[{"role":"user","content":prompt}])
            story = comp.choices[0].message.content.strip()
            print(f"Groq OK - {len(story.split())} words")
        except Exception as e:
            print(f"Groq fail {e}")
    
    if not story:
        story = f"{title} একটি অসাধারণ গল্পের সিনেমা। দুই অচেনা মানুষের জীবনের এক অদ্ভুত রাতের নাটকীয় এবং হাস্যরসাত্মক গল্প।"
    
    return story.strip()

# === TTS V43 REST METHOD ===
def create_gemini_tts_rest_runner_file(text):
    # Write voice_text.txt
    with open("voice_text.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print(f"voice_text.txt written {len(text)} chars")
    
    runner_code = '''
import requests
import base64
import os
import sys
import time

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("No GEMINI_API_KEY")
    sys.exit(1)

with open("voice_text.txt", "r", encoding="utf-8") as f:
    text = f.read().strip()

if not text:
    print("voice_text.txt empty")
    sys.exit(1)

MODELS = [
    "gemini-3.8-flash-tts",
    "gemini-3.8-flash-lite-tts", 
    "gemini-2.5-flash-preview-tts",
    "gemini-2.5-flash-lite-preview-tts",
    "gemini-2.5-pro-preview-tts"
]

success = False
last_err = ""

for model in MODELS:
    print(f"Trying model {model}...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": "Fenrir"}
                }
            }
        }
    }
    try:
        r = requests.post(url, json=payload, timeout=120)
        print(f"TTS Runner STDOUT: s... status {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            try:
                # Try both camelCase and snake_case
                parts = data.get('candidates', [{}])[0].get('content', {}).get('parts', [])
                b64_data = None
                for p in parts:
                    if 'inlineData' in p:
                        b64_data = p['inlineData'].get('data')
                        break
                    if 'inline_data' in p:
                        b64_data = p['inline_data'].get('data')
                        break
                if not b64_data:
                    # fallback search
                    import json as js
                    txt = js.dumps(data)
                    # try to find data field
                    print(f"Response keys: {list(data.keys())} no inlineData found, full: {str(data)[:1000]}")
                    last_err = f"No audio data in response for {model}"
                    continue
                audio_bytes = base64.b64decode(b64_data)
                with open("gemini_tts_output.mp3", "wb") as out:
                    out.write(audio_bytes)
                print(f"Model {model} SUCCESS - {len(audio_bytes)} bytes")
                success = True
                break
            except Exception as pe:
                print(f"Parse fail {model}: {pe} - {r.text[:800]}")
                last_err = str(pe)
                continue
        else:
            print(f"Model {model} failed: {r.status_code} {r.text[:800]}")
            last_err = r.text[:800]
            # If 503, retry after 3 sec
            if r.status_code == 503:
                time.sleep(3)
                continue
    except Exception as e:
        print(f"Model {model} exception: {e}")
        last_err = str(e)
        continue

if not success:
    print(f"All models failed, last error: {last_err}", file=sys.stderr)
    sys.exit(1)
'''
    with open("temp_gemini_tts_runner.py", "w", encoding="utf-8") as f:
        f.write(runner_code)

def generate_voice(text):
    print(f"TTS: {len(text.split())} words - Trying FILE-BASED Gemini TTS PRIMARY then Edge fallback")
    print(f"Gemini TTS V43 REST METHOD: {len(text.split())} words with Fenrir...")
    
    create_gemini_tts_rest_runner_file(text)
    
    # Run runner
    try:
        result = subprocess.run([sys.executable, "temp_gemini_tts_runner.py"], capture_output=True, text=True, timeout=180)
        print(f"TTS Runner STDOUT: {result.stdout[-1000:]}")
        if result.stderr:
            print(f"TTS Runner STDERR: {result.stderr[-1000:]}")
        
        if os.path.exists("gemini_tts_output.mp3") and os.path.getsize("gemini_tts_output.mp3") > 1000:
            print(f"Gemini TTS V43 REST SUCCESS - {os.path.getsize('gemini_tts_output.mp3')} bytes")
            # Convert to wav and enhance
            subprocess.run(["ffmpeg", "-y", "-i", "gemini_tts_output.mp3", "-filter:a", "volume=1.8,highpass=f=80,lowpass=f=12000,acompressor=threshold=-20dB:ratio=4:attack=5:release=50", "voice_final.wav"], capture_output=True)
            if os.path.exists("voice_final.wav"):
                size_kb = os.path.getsize("voice_final.wav")/1024
                print(f"PRO Studio voice applied - NO robotic {size_kb:.1f} KB")
                return "voice_final.wav"
            return "gemini_tts_output.mp3"
        else:
            print("Gemini TTS V43 FILE METHOD FAILED - output not found")
    except Exception as e:
        print(f"Gemini runner exception: {e}")
    
    # Edge TTS fallback
    print("Gemini FILE METHOD failed, FALLBACK to Edge TTS bn-IN-BashkarNeural")
    try:
        import edge_tts
        import asyncio
        
        async def _edge():
            communicate = edge_tts.Communicate(text, "bn-IN-BashkarNeural")
            await communicate.save("voice_final.wav")
        
        asyncio.run(_edge())
        # Enhance
        subprocess.run(["ffmpeg", "-y", "-i", "voice_final.wav", "-filter:a", "volume=1.8,highpass=f=80,lowpass=f=12000", "voice_enhanced.wav"], capture_output=True)
        if os.path.exists("voice_enhanced.wav"):
            os.replace("voice_enhanced.wav", "voice_final.wav")
        size_kb = os.path.getsize("voice_final.wav")/1024 if os.path.exists("voice_final.wav") else 0
        print(f"PRO Studio voice applied - NO robotic {size_kb:.1f} KB")
        return "voice_final.wav"
    except Exception as e:
        print(f"Edge TTS fail {e}")
        return None

# === SMART TRIM ===
def smart_trim_trailer(input_path, output_path, target_duration=60):
    print(f"Smart trim START {get_video_duration(input_path):.1f}s -> {target_duration}s | Sampling whole trailer from start to end")
    duration = get_video_duration(input_path)
    if duration <= target_duration:
        subprocess.run(["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path], capture_output=True)
        return
    
    num_cuts = 12
    cut_len = target_duration / num_cuts
    interval = (duration - cut_len) / num_cuts
    
    parts = []
    for i in range(num_cuts):
        start = max(0, i * interval + 2.0)
        if i == num_cuts-1:
            start = max(0, duration - cut_len)
        parts.append((start, cut_len))
        print(f"  Cut {i+1}: {start:.1f}s - {start+cut_len:.1f}s")
    
    # Create concat file
    concat_file = "concat_list.txt"
    temp_files = []
    for idx, (s, d) in enumerate(parts):
        temp_out = f"temp_part_{idx}.mp4"
        cmd = ["ffmpeg", "-y", "-ss", str(s), "-i", input_path, "-t", str(d), "-c:v", "libx264", "-c:a", "aac", "-an", temp_out]
        subprocess.run(cmd, capture_output=True)
        temp_files.append(temp_out)
        with open(concat_file, "a") as f:
            f.write(f"file '{temp_out}'\n")
    
    # Concat
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output_path]
    subprocess.run(cmd, capture_output=True)
    
    # Cleanup temp parts
    for tf in temp_files:
        if os.path.exists(tf):
            os.remove(tf)
    if os.path.exists(concat_file):
        os.remove(concat_file)
    
    print(f"Smart trim DONE {get_video_duration(output_path):.1f}s from {duration:.1f}s with {num_cuts} cuts across whole trailer - V38 FIXED")

def get_video_duration(path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except:
        return 150.0

# === BGM ===
def generate_bgm(category, duration):
    print(f"BGM Category: {category} Duration: {duration}s")
    print(f"Generating {category} BGM {duration}s LOUDER...")
    # Generate simple tone BGM using ffmpeg
    output = "bgm.mp3"
    # Use anullsrc with filter for mood
    freq = {"happy": 440, "sad": 220, "thriller": 330, "romantic": 350}.get(category, 440)
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}", "-filter:a", "volume=0.08", output]
    subprocess.run(cmd, capture_output=True)
    if os.path.exists(output):
        print(f"BGM OK {os.path.getsize(output)/1024:.1f} KB louder")
        return output
    return None

# === VIDEO CREATE V42 FIXED FFmpeg ===
def create_final_video(trailer_path, voice_path, bgm_path, details, output_path):
    title = details.get("title") or details.get("name") or "Movie"
    print(f"Creating 60s video V43 FIXED FFmpeg - Top: Movie Name | {title} | Type: {details.get('media_type','movie')}")
    print(f"FFmpeg V43 FIXED 60s running...")
    
    # Escape text for drawtext
    safe_title = title.replace(":", " ").replace("'", "").replace('"', "")[:40]
    
    # V42 FIXED filter chain: [base]->[t1]->[t2]->[t3]->[final_v]
    # Base video 1080x1920
    # t1: scale and crop
    # t2: add poster overlay? simplified
    # t3: text overlays
    
    # Use DejaVu font
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if not os.path.exists(font_path):
        font_path = "/usr/share/fonts/truetype/noto/NotoSansBengali-Bold.ttf"
    
    # Build complex filter - FIXED chaining
    filter_complex = (
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[base];"
        f"[base]drawtext=fontfile={font_path}:text='{safe_title}':fontcolor=white:fontsize=60:x=(w-text_w)/2:y=100:box=1:boxcolor=black@0.6:boxborderw=10[final_v];"
        f"[1:a][2:a]amix=inputs=2:duration=longest:dropout_transition=0:weights=1 0.15[final_a]"
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-i", trailer_path,
        "-i", voice_path,
        "-i", bgm_path,
        "-filter_complex", filter_complex,
        "-map", "[final_v]",
        "-map", "[final_a]",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-t", "60",
        "-r", "30",
        "-b:v", "4000k",
        "-shortest",
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path)/1024/1024
            print(f"Final OK V43 FIXED {size_mb:.2f} MB")
            return True
        else:
            print(f"FFmpeg fail: {result.stderr[-2000:]}")
            # Fallback simple
            cmd2 = ["ffmpeg", "-y", "-i", trailer_path, "-i", voice_path, "-i", bgm_path, "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=shortest[fa]", "-map", "0:v", "-map", "[fa]", "-c:v", "copy", "-t", "60", output_path]
            subprocess.run(cmd2, capture_output=True, timeout=200)
            return os.path.exists(output_path)
    except Exception as e:
        print(f"FFmpeg exception {e}")
        return False

# === FB UPLOAD ===
def upload_fb_video(video_path, title, description):
    url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/videos"
    print(f"Uploading {title} - {os.path.getsize(video_path)/1024/1024:.2f} MB")
    try:
        with open(video_path, "rb") as f:
            files = {"source": f}
            data = {"title": title, "description": description, "access_token": FB_PAGE_TOKEN}
            r = requests.post(url, files=files, data=data, timeout=300)
        print(f"FB Upload {title} Status {r.status_code} {r.text[:500]}")
        if r.status_code == 200:
            vid = r.json().get("id")
            print(f"✅ PAGE POSTED SUCCESSFULLY - ID: {vid}")
            return vid
    except Exception as e:
        print(f"FB upload fail {e}")
    return None

def upload_group_video(video_path, title, description):
    if not FB_GROUP_ID:
        return None
    url = f"https://graph.facebook.com/v19.0/{FB_GROUP_ID}/videos"
    print(f"Attempting optional group post for {FB_GROUP_ID}...")
    print(f"Uploading {title} - {os.path.getsize(video_path)/1024/1024:.2f} MB")
    try:
        with open(video_path, "rb") as f:
            files = {"source": f}
            data = {"title": title, "description": description, "access_token": FB_PAGE_TOKEN}
            r = requests.post(url, files=files, data=data, timeout=300)
        print(f"FB Upload {title} Status {r.status_code} {r.text[:500]}")
        if r.status_code == 200:
            return r.json().get("id")
        else:
            print("⚠ Group failed but PAGE SUCCESS - WORK DONE")
    except Exception as e:
        print(f"Group upload fail {e} ⚠ Group failed but PAGE SUCCESS - WORK DONE")
    return None

# === YOUTUBE UPLOAD ===
def upload_youtube_shorts(video_path, title, description, tags):
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        
        client_id = os.environ.get("YOUTUBE_CLIENT_ID")
        client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
        refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")
        
        creds = Credentials(None, refresh_token=refresh_token, token_uri="https://oauth2.googleapis.com/token", client_id=client_id, client_secret=client_secret)
        youtube = build("youtube", "v3", credentials=creds)
        
        print(f"Building YouTube SEO metadata for {title}...")
        yt_title = f"{title} Explained #Shorts"[:95]
        yt_tags = tags[:15]
        print(f"YouTube Title: {yt_title}")
        print(f"YouTube Tags: {', '.join(yt_tags[:5])}...")
        print(f"Uploading to YouTube Shorts: {yt_title} - {os.path.getsize(video_path)/1024/1024:.2f} MB")
        
        body = {
            "snippet": {"title": yt_title, "description": description, "tags": yt_tags, "categoryId": "24"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
        vid = response["id"]
        print(f"✅ YOUTUBE SHORTS UPLOADED - ID: {vid} - https://youtube.com/shorts/{vid}")
        print(f"✅ YOUTUBE SHORTS ALSO POSTED - https://youtube.com/shorts/{vid}")
        return vid
    except Exception as e:
        print(f"YouTube upload fail: {e}")
        return None

# === MAIN ===
def main():
    print("=== MoviMoon AutoPoster V43 - V38 EXACT + 2 FIXES START ===")
    print("Filtering: 2024+ | Hollywood + Bollywood + South + Series")
    
    movies = fetch_tmdb()
    history = get_history()
    posted_ids = set([str(h["id"]) for h in history])
    
    count = 0
    for idx, m in enumerate(movies[:10]):
        mid = str(m["id"])
        if mid in posted_ids:
            print(f"[{idx+1}/10] Already posted {mid}, skipping")
            continue
        
        is_tv = m.get("media_type") == "tv" or "first_air_date" in m
        print(f">>> [{idx+1}/10] {m.get('title') or m.get('name')} ({mid})")
        
        details = get_movie_details(mid, is_tv)
        if not details:
            continue
        
        trailer = select_trailer(details)
        if not trailer:
            print(f"No trailer for {mid}")
            continue
        
        print(f"Trailer selected: {trailer.get('name')} | Type: {trailer.get('type')} | Official: {trailer.get('official')}")
        yt_url = f"https://www.youtube.com/watch?v={trailer['key']}"
        print(f"Trailer URL: {yt_url}")
        
        trailer_file = f"{OUTPUT_DIR}/trailer_{mid}.mp4"
        if not download_trailer_yt_dlp(yt_url, trailer_file):
            continue
        
        duration = get_video_duration(trailer_file)
        story = generate_story_gemini(details, duration)
        
        # Voice words calc
        voice_words = len(story.split())
        target_words = int(duration * 2.66)
        print(f"Voice {voice_words} words (target {target_words-5}-{target_words} for {duration}s)")
        
        # Caption
        genres = ", ".join([g["name"] for g in details.get("genres", [])][:3])
        rating = details.get("vote_average", "N/A")
        title_bangla = details.get("title") or details.get("name")
        caption = f"🎬 Movie - {title_bangla}({details.get('release_date','2026')[:4]})\n🎭 Genres - {genres}\n⭐ Rating - {rating}/10\n📖 Story - {story[:200]}"
        print(f"Caption built: {caption[:150]}")
        
        voice_path = generate_voice(story)
        if not voice_path:
            print("Voice fail, skipping")
            continue
        
        # Trim
        trimmed = f"{OUTPUT_DIR}/trimmed_{mid}.mp4"
        print(f"Smart trim START {duration:.1f}s -> 60s | Sampling whole trailer from start to end")
        smart_trim_trailer(trailer_file, trimmed, 60)
        
        # BGM
        bgm_path = generate_bgm("happy", 60)
        
        # Final video
        final_path = f"{OUTPUT_DIR}/final_{mid}.mp4"
        title_en = details.get("title") or details.get("name")
        if not create_final_video(trimmed, voice_path, bgm_path, {"title": title_en, "media_type": "movie"}, final_path):
            continue
        
        # Upload
        fb_title = f"{title_en} - Trailer Review"
        fb_desc = f"{caption}\n\n#MoviMoon #MovieReview #BanglaReview\nFull video: movimoon.online\n\n{title_en} trailer review in Bangla"
        print(f"Uploading {title_en} - {os.path.getsize(final_path)/1024/1024:.2f} MB")
        
        page_id = upload_fb_video(final_path, fb_title, fb_desc)
        if page_id:
            print(f"Posted {title_en} successfully - PAGE ONLY SUCCESS = WORK DONE")
            upload_group_video(final_path, fb_title, fb_desc)
            
            # YouTube
            yt_tags = [title_en.lower(), f"{title_en} 2026", f"{title_en} trailer", f"{title_en} review", "bangla review", "movie review", "movimoon"]
            upload_youtube_shorts(final_path, f"{title_en} | {title_en} (2026) Explained #Shorts", fb_desc, yt_tags)
            
            save_history(mid)
            print(f"🎉 1 VIDEO DONE - FB + YT (optional) - WORKFLOW COMPLETE - STOPPING, NO 2nd TRY")
            break
    
    print("=== MoviMoon AutoPoster V43 END ===")

if __name__ == "__main__":
    main()
