"""
MoviMoon AutoPoster V44 HOTFIX - History Bug Fixed
- V38 EXACT + V43 REST TTS + V44 History tolerant
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

print("=== MoviMoon Bot - V44 HOTFIX | History Bug Fixed ===")

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
    
    unique = {}
    for m in all_movies:
        unique[m["id"]] = m
    print(f"Total fetched {len(all_movies)}, unique {len(unique)}")
    return list(unique.values())[:90]

def get_history():
    if not os.path.exists(HISTORY_FILE):
        print(f"History file {HISTORY_FILE} not found, starting fresh")
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"History raw type: {type(data)} len: {len(data) if isinstance(data,list) else 'not list'}")
            if isinstance(data, list) and len(data)>0:
                print(f"History first item sample: {str(data[0])[:200]} type: {type(data[0])}")
            return data
    except Exception as e:
        print(f"History read fail {e}, resetting")
        return []

def extract_posted_ids(history_raw):
    ids = set()
    for h in history_raw:
        try:
            if isinstance(h, dict):
                vid = h.get("id") or h.get("movie_id") or h.get("movieId")
                if vid is not None:
                    ids.add(str(vid))
            elif isinstance(h, (int, float)):
                ids.add(str(int(h)))
            elif isinstance(h, str):
                h_clean = h.strip().strip('"').strip("'")
                if h_clean.isdigit():
                    ids.add(str(h_clean))
                else:
                    try:
                        inner = json.loads(h)
                        if isinstance(inner, dict) and "id" in inner:
                            ids.add(str(inner["id"]))
                        else:
                            ids.add(str(h_clean))
                    except:
                        ids.add(str(h_clean))
        except Exception as e:
            print(f"Skip history item {h}: {e}")
            continue
    print(f"Extracted {len(ids)} posted IDs from history")
    return ids

def save_history(movie_id):
    hist_raw = get_history()
    new_entry = {"id": int(movie_id) if str(movie_id).isdigit() else movie_id, "date": datetime.now().isoformat()}
    converted = []
    for h in hist_raw:
        if isinstance(h, dict):
            converted.append(h)
        elif isinstance(h, (int,str)):
            try:
                converted.append({"id": int(h) if str(h).isdigit() else h, "date": "old"})
            except:
                converted.append({"id": h, "date": "old"})
    converted.append(new_entry)
    converted = converted[-500:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(converted, f, indent=2)
    print(f"History saved {movie_id}, total now {len(converted)}")

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

def select_trailer(details):
    videos = details.get("videos", {}).get("results", [])
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

def parse_proxy_list():
    proxies = []
    if YOUTUBE_PROXY_LIST:
        for line in YOUTUBE_PROXY_LIST.splitlines():
            line=line.strip()
            if not line:
                continue
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
                        print(f"  FAIL {label}: {result.stderr[-400:] if result.stderr else result.stdout[-400:]}")
                except Exception as e:
                    print(f"  FAIL {label}: {e}")
    
    print("All YT-DLP methods failed")
    return False

def generate_story_gemini(details, duration):
    title = details.get("title") or details.get("name") or "Movie"
    overview = details.get("overview") or ""
    target_words = int(duration * 2.66)
    target_min = max(120, target_words-5)
    target_max = target_words+5
    print(f"Trailer duration {duration}s -> target {target_min}-{target_max} words")
    
    prompt = f"""
    Write a Bangla movie review voiceover script for "{title}".
    Overview: {overview}
    - Length MUST be {target_min} to {target_max} words
    - Use simple Bangla, engaging, dramatic
    - No English except movie name
    - Story only, no intro like 'Hello friends'
    - Word count strictly {target_min}-{target_max}
    """
    
    story = None
    models_to_try = ["gemini-3.5-flash-lite","gemini-3.1-flash-lite", "gemini-2.0-flash-lite"]
    try:
        import google.generativeai as genai_old
        genai_old.configure(api_key=GEMINI_API_KEY)
        for model_name in models_to_try:
            try:
                model = genai_old.GenerativeModel(model_name)
                resp = model.generate_content(prompt)
                text = resp.text.strip()
                words = len(text.split())
                print(f"Gemini {model_name} OK - {words} words story: {text[:60]}")
                story = text
                if words < target_min:
                    for loop in range(1,4):
                        print(f"Loop {loop}: {words} words, expanding...")
                        expand_prompt = f"Previous story: {text}\nExpand it to exactly {target_min}-{target_max} words, keep Bangla: {prompt}"
                        resp2 = model.generate_content(expand_prompt)
                        text2 = resp2.text.strip()
                        words2 = len(text2.split())
                        if words2 >= target_min:
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

def create_gemini_tts_rest_runner_file(text):
    with open("voice_text.txt", "w", encoding="utf-8") as f:
        f.write(text)
    runner_code = '''
import requests, base64, os, sys, time
api_key = os.environ.get("GEMINI_API_KEY")
with open("voice_text.txt", "r", encoding="utf-8") as f:
    text = f.read().strip()
MODELS = ["gemini-3.8-flash-tts","gemini-3.8-flash-lite-tts","gemini-2.5-flash-preview-tts","gemini-2.5-flash-lite-preview-tts","gemini-2.5-pro-preview-tts"]
for model in MODELS:
    print(f"Trying model {model}...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": text}]}],"generationConfig": {"responseModalities": ["AUDIO"],"speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Fenrir"}}}}}
    try:
        r = requests.post(url, json=payload, timeout=120)
        print(f"TTS Runner status {r.status_code} for {model}")
        if r.status_code == 200:
            data = r.json()
            parts = data.get('candidates', [{}])[0].get('content', {}).get('parts', [])
            b64_data = None
            for p in parts:
                if 'inlineData' in p:
                    b64_data = p['inlineData'].get('data'); break
                if 'inline_data' in p:
                    b64_data = p['inline_data'].get('data'); break
            if not b64_data:
                print(f"No inlineData for {model}"); continue
            audio_bytes = base64.b64decode(b64_data)
            open("gemini_tts_output.mp3","wb").write(audio_bytes)
            print(f"Model {model} SUCCESS - {len(audio_bytes)} bytes")
            sys.exit(0)
        else:
            print(f"Model {model} failed: {r.status_code} {r.text[:800]}")
    except Exception as e:
        print(f"Model {model} exception: {e}")
sys.exit(1)
'''
    with open("temp_gemini_tts_runner.py", "w", encoding="utf-8") as f:
        f.write(runner_code)

def generate_voice(text):
    print(f"TTS: {len(text.split())} words - REST TTS")
    create_gemini_tts_rest_runner_file(text)
    try:
        result = subprocess.run([sys.executable, "temp_gemini_tts_runner.py"], capture_output=True, text=True, timeout=180)
        print(f"TTS Runner STDOUT: {result.stdout[-1500:]}")
        if os.path.exists("gemini_tts_output.mp3") and os.path.getsize("gemini_tts_output.mp3") > 1000:
            print(f"Gemini TTS V44 REST SUCCESS - {os.path.getsize('gemini_tts_output.mp3')} bytes")
            subprocess.run(["ffmpeg", "-y", "-i", "gemini_tts_output.mp3", "-filter:a", "volume=1.8,highpass=f=80,lowpass=f=12000,acompressor=threshold=-20dB:ratio=4:attack=5:release=50", "voice_final.wav"], capture_output=True)
            return "voice_final.wav" if os.path.exists("voice_final.wav") else "gemini_tts_output.mp3"
    except Exception as e:
        print(f"Gemini runner exception: {e}")
    print("FALLBACK to Edge TTS")
    try:
        import edge_tts, asyncio
        async def _edge():
            communicate = edge_tts.Communicate(text, "bn-IN-BashkarNeural")
            await communicate.save("voice_final.wav")
        asyncio.run(_edge())
        return "voice_final.wav"
    except Exception as e:
        print(f"Edge TTS fail {e}")
        return None

def smart_trim_trailer(input_path, output_path, target_duration=60):
    duration = get_video_duration(input_path)
    if duration <= target_duration:
        subprocess.run(["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path], capture_output=True)
        return
    num_cuts = 12
    cut_len = target_duration / num_cuts
    interval = (duration - cut_len) / num_cuts
    concat_file = "concat_list.txt"
    if os.path.exists(concat_file):
        os.remove(concat_file)
    temp_files = []
    for idx in range(num_cuts):
        start = max(0, idx * interval + 2.0)
        if idx == num_cuts-1:
            start = max(0, duration - cut_len)
        temp_out = f"temp_part_{idx}.mp4"
        subprocess.run(["ffmpeg", "-y", "-ss", str(start), "-i", input_path, "-t", str(cut_len), "-c:v", "libx264", "-c:a", "aac", "-an", temp_out], capture_output=True)
        temp_files.append(temp_out)
        with open(concat_file, "a") as f:
            f.write(f"file '{temp_out}'\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output_path], capture_output=True)
    for tf in temp_files:
        if os.path.exists(tf):
            os.remove(tf)
    if os.path.exists(concat_file):
        os.remove(concat_file)

def get_video_duration(path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except:
        return 150.0

def generate_bgm(category, duration):
    output = "bgm.mp3"
    freq = {"happy": 440, "sad": 220, "thriller": 330, "romantic": 350}.get(category, 440)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}", "-filter:a", "volume=0.08", output], capture_output=True)
    return output if os.path.exists(output) else None

def create_final_video(trailer_path, voice_path, bgm_path, details, output_path):
    title = details.get("title") or details.get("name") or "Movie"
    safe_title = title.replace(":", " ").replace("'", "").replace('"', "")[:40]
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    filter_complex = f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[base];[base]drawtext=fontfile={font_path}:text='{safe_title}':fontcolor=white:fontsize=60:x=(w-text_w)/2:y=100:box=1:boxcolor=black@0.6:boxborderw=10[final_v];[1:a][2:a]amix=inputs=2:duration=longest:dropout_transition=0:weights=1 0.15[final_a]"
    cmd = ["ffmpeg", "-y","-i", trailer_path,"-i", voice_path,"-i", bgm_path,"-filter_complex", filter_complex,"-map", "[final_v]","-map", "[final_a]","-c:v", "libx264","-c:a", "aac","-t", "60","-r", "30","-b:v", "4000k","-shortest", output_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if os.path.exists(output_path):
        print(f"Final OK V44 {os.path.getsize(output_path)/1024/1024:.2f} MB")
        return True
    print(f"FFmpeg fail {result.stderr[-1000:]}")
    return False

def upload_fb_video(video_path, title, description):
    url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/videos"
    try:
        with open(video_path, "rb") as f:
            files = {"source": f}
            data = {"title": title, "description": description, "access_token": FB_PAGE_TOKEN}
            r = requests.post(url, files=files, data=data, timeout=300)
        print(f"FB Upload {r.status_code} {r.text[:500]}")
        if r.status_code == 200:
            return r.json().get("id")
    except Exception as e:
        print(f"FB upload fail {e}")
    return None

def upload_group_video(video_path, title, description):
    if not FB_GROUP_ID:
        return None
    url = f"https://graph.facebook.com/v19.0/{FB_GROUP_ID}/videos"
    try:
        with open(video_path, "rb") as f:
            files = {"source": f}
            data = {"title": title, "description": description, "access_token": FB_PAGE_TOKEN}
            r = requests.post(url, files=files, data=data, timeout=300)
        print(f"Group Upload {r.status_code} {r.text[:500]}")
        return r.json().get("id") if r.status_code==200 else None
    except Exception as e:
        print(f"Group fail {e}")
    return None

def upload_youtube_shorts(video_path, title, description, tags):
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        creds = Credentials(None, refresh_token=os.environ.get("YOUTUBE_REFRESH_TOKEN"), token_uri="https://oauth2.googleapis.com/token", client_id=os.environ.get("YOUTUBE_CLIENT_ID"), client_secret=os.environ.get("YOUTUBE_CLIENT_SECRET"))
        youtube = build("youtube", "v3", credentials=creds)
        body = {"snippet": {"title": f"{title} Explained #Shorts"[:95], "description": description, "tags": tags, "categoryId": "24"},"status": {"privacyStatus": "public"}}
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
        print(f"YT OK {response['id']}")
        return response["id"]
    except Exception as e:
        print(f"YouTube fail {e}")
        return None

def main():
    print("=== MoviMoon AutoPoster V44 - History Bug Fixed START ===")
    movies = fetch_tmdb()
    history_raw = get_history()
    posted_ids = extract_posted_ids(history_raw)
    for idx, m in enumerate(movies[:10]):
        mid = str(m["id"])
        if mid in posted_ids:
            print(f"[{idx+1}/10] Already posted {mid}, skipping")
            continue
        is_tv = m.get("media_type") == "tv" or "first_air_date" in m
        print(f">>> [{idx+1}/10] {m.get('title') or m.get('name')} ({mid})")
        details = get_movie_details(mid, is_tv)
        trailer = select_trailer(details)
        if not trailer:
            print(f"No trailer {mid}")
            continue
        yt_url = f"https://www.youtube.com/watch?v={trailer['key']}"
        trailer_file = f"{OUTPUT_DIR}/trailer_{mid}.mp4"
        if not download_trailer_yt_dlp(yt_url, trailer_file):
            continue
        duration = get_video_duration(trailer_file)
        story = generate_story_gemini(details, duration)
        genres = ", ".join([g["name"] for g in details.get("genres", [])][:3])
        caption = f"Movie - {details.get('title') or details.get('name')} Rating - {details.get('vote_average','N/A')}/10 Story - {story[:200]}"
        voice_path = generate_voice(story)
        if not voice_path:
            continue
        trimmed = f"{OUTPUT_DIR}/trimmed_{mid}.mp4"
        smart_trim_trailer(trailer_file, trimmed, 60)
        bgm_path = generate_bgm("happy", 60)
        final_path = f"{OUTPUT_DIR}/final_{mid}.mp4"
        title_en = details.get("title") or details.get("name")
        if not create_final_video(trimmed, voice_path, bgm_path, {"title": title_en}, final_path):
            continue
        fb_title = f"{title_en} - Trailer Review"
        fb_desc = f"{caption}\n\n#MoviMoon #MovieReview\n{title_en} trailer review in Bangla"
        page_id = upload_fb_video(final_path, fb_title, fb_desc)
        if page_id:
            upload_group_video(final_path, fb_title, fb_desc)
            upload_youtube_shorts(final_path, title_en, fb_desc, [title_en.lower(), "movie review"])
            save_history(mid)
            print(f"🎉 1 VIDEO DONE - STOPPING")
            break
    print("=== MoviMoon AutoPoster V44 END ===")

if __name__ == "__main__":
    main()
