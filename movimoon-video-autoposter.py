import os, requests, random, re, time, asyncio, json, subprocess
from datetime import datetime, timedelta
from pathlib import Path

print("=== MoviMoon Bot Starting - 9:16 HD FINAL VERSION ===")

try:
    import edge_tts
    print("edge_tts imported OK")
except Exception as e:
    print(f"edge_tts import failed: {e}")
    import sys; sys.exit(1)

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
FB_GROUP_ID = os.getenv("FB_GROUP_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

VOICE = "bn-IN-BashkarNeural"
RATE = "+28%"  # slower for 1min = more clear
PITCH = "+2Hz"
VOLUME = "+30%"
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
    print(f"Filtering: Only {min_year}+ New + Trending")
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
        print(f"Using cookies.txt - {Path('cookies.txt').stat().st_size} bytes")
        return '--cookies cookies.txt'
    print("No valid cookies.txt - trying without")
    return ''

def download_via_ytdlp_fixed(youtube_url, output="trailer.mp4"):
    print(f"\n=== YT-DLP HD FIXED for {youtube_url} ===")
    Path(output).unlink(missing_ok=True)
    cookie_arg = get_cookie_arg()
    deno_bin = f"{os.path.expanduser('~')}/.deno/bin/deno"
    js_arg = f"--js-runtimes deno:{deno_bin}" if Path(deno_bin).exists() else "--js-runtimes deno"
    
    # UPDATED: Now tries 1080p -> 720p minimum HD
    strategies = [
        f'yt-dlp {cookie_arg} {js_arg} --extractor-args "youtube:player_client=android,web" -f "bestvideo[height>=720][height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080][ext=mp4]+bestaudio/best[height>=720]" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --force-ipv4',
        f'yt-dlp {cookie_arg} --extractor-args "youtube:player_client=android" -f "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --force-ipv4',
        f'yt-dlp {cookie_arg} --extractor-args "youtube:player_client=ios" -f "best[height<=1080]" -o "{output}" "{youtube_url}" --no-playlist --force-ipv4',
        f'yt-dlp {cookie_arg} -f "best[height>=720][ext=mp4]/best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --force-ipv4',
    ]
    
    for i, cmd in enumerate(strategies, 1):
        print(f"\n[Strategy {i}/{len(strategies)}] trying HD...")
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=180)
            if result.stdout: print(f"OUT: {result.stdout[-400:]}")
            if result.stderr: print(f"ERR: {result.stderr[-600:]}")
            if Path(output).exists() and Path(output).stat().st_size > 50000:
                print(f"✅ YT-DLP HD SUCCESS {i} - {Path(output).stat().st_size/1024/1024:.2f} MB")
                return output
            Path(output).unlink(missing_ok=True)
        except Exception as e:
            print(f"Strategy {i} exception: {e}")
            continue
        time.sleep(2)
    print("All yt-dlp strategies failed")
    return None

def download_via_cobalt_fixed(youtube_url, output="trailer.mp4"):
    print(f"\n=== COBALT HD for {youtube_url} ===")
    Path(output).unlink(missing_ok=True)
    instances = ["https://api.cobalt.tools/api/json", "https://co.wuk.sh/api/json"]
    for api in instances:
        try:
            print(f"Trying {api}")
            payload = {"url": youtube_url, "vCodec": "h264", "vQuality": "1080", "isAudioOnly": False}
            r = requests.post(api, json=payload, headers={"Accept":"application/json","Content-Type":"application/json"}, timeout=20)
            print(f"Status {r.status_code}: {r.text[:300]}")
            if r.status_code == 200:
                dl_url = r.json().get("url")
                if dl_url:
                    with requests.get(dl_url, stream=True, timeout=90) as dl:
                        with open(output,'wb') as f:
                            for chunk in dl.iter_content(1024*1024):
                                if chunk: f.write(chunk)
                    if Path(output).exists() and Path(output).stat().st_size > 50000:
                        print(f"✅ Cobalt HD SUCCESS")
                        return output
        except Exception as e:
            print(f"Cobalt {api} error {e}")
            continue
    return None

def download_trailer(youtube_url, output="trailer.mp4"):
    res = download_via_ytdlp_fixed(youtube_url, output)
    if res: return res
    res = download_via_cobalt_fixed(youtube_url, output)
    if res: return res
    print("ALL DOWNLOAD METHODS FAILED")
    return None

def download_movie_poster(movie, output="poster.jpg"):
    """NEW: Download TMDB poster for 9:16 blurred background"""
    try:
        poster_path = movie.get("poster_path")
        if not poster_path:
            print("No poster_path")
            return None
        url = f"https://image.tmdb.org/t/p/w780{poster_path}"
        print(f"Downloading poster: {url}")
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            with open(output, 'wb') as f:
                f.write(r.content)
            if Path(output).exists() and Path(output).stat().st_size > 1000:
                print(f"✅ Poster downloaded {Path(output).stat().st_size/1024:.1f} KB")
                return output
    except Exception as e:
        print(f"Poster download error: {e}")
    return None

def trim_trailer_to_60s(input_path, output_path="trailer_60s.mp4"):
    try:
        if Path(output_path).exists(): Path(output_path).unlink()
        cmd = f'ffmpeg -y -i "{input_path}" -t 60 -c:v libx264 -preset fast -crf 23 -c:a aac "{output_path}"'
        subprocess.run(cmd, shell=True, capture_output=True, timeout=90)
        if Path(output_path).exists(): return output_path
        return input_path
    except Exception as e:
        print(f"Trim error {e}")
        return input_path

def call_gemini_video_script(title, year, m_type, rating, overview, link):
    if not GEMINI_API_KEY:
        voice = f"বন্ধুরা, কেমন আছেন সবাই? আজকে কথা বলব {year} সালের বহুল আলোচিত সিনেমা {title} নিয়ে। এই সিনেমার গল্পটা এতটাই টানটান উত্তেজনায় ভরা যে একবার দেখা শুরু করলে শেষ না করে উঠতে পারবেন না। প্রধান চরিত্রের অসাধারণ অভিনয়, দুর্দান্ত সিনেমাটোগ্রাফি এবং ব্যাকগ্রাউন্ড মিউজিক আপনাকে এক মুহূর্তের জন্যও বোর হতে দেবে না। বিশেষ করে শেষের টুইস্টটা আপনার মাথা ঘুরিয়ে দেবে। আইএমডিবিতে {rating} রেটিং পাওয়া এই সিনেমাটি যারা থ্রিলার এবং অ্যাকশন পছন্দ করেন তাদের জন্য মাস্ট ওয়াচ। পুরো সিনেমাটির এইচডি প্রিন্ট, বিস্তারিত রিভিউ এবং ডাউনলোড লিংক পেয়ে যাবেন আমাদের ওয়েবসাইট মুভিমুন ডট অনলাইন এ। এখনই ভিজিট করুন।"
        caption = f"🎬 {title} ({year}) - {rating}/10\n\n{overview[:200]}\n\n👉 ফুল রিভিউ: {link}\n\n#MovieReview #MoviMoon"
        return voice, caption

    prompt = f"""
You are MoviMoon's Lead Professional Bengali Movie Critic & Voiceover Script Writer. Your voiceover will be used for EDGE TTS (BashkarNeural, +28% speed). It MUST be exactly 1 minute long.

MOVIE DATA:
Title: {title}
Year: {year}
Type: {m_type} (movie/tv)
Rating: {rating}/10
Plot: {overview}
Site Link: {link}

TASK: Write a HIGHLY PROFESSIONAL, CINEMATIC 1-MINUTE voiceover script.

STRICT RULES FOR VOICEOVER (Bengali, 140-160 words, 60 seconds):
1. Language: Pure natural spoken Bengali (mix of চলিত ভাষা). No English words title alos Bengali.
2. Length: 140 to 160 words MUST. Count internally. This is for 60 seconds.
3. Structure (5 parts):
   - [HOOK 0-8s]: Start with "বন্ধুরা, কেমন আছেন সবাই? আজকে কথা বলব..." or explosive hook about {title}
   - [STORY 8-25s]: What is the story? Use plot but make it thrilling, don't spoil ending.
   - [PERFORMANCE & TECH 25-45s]: Talk about Acting, Direction, BGM, VFX, Cinematography. Mention {year} and why it's trending. Mention rating {rating} if >7.
   - [WHY WATCH 45-53s]: Why should audience watch? Who will love it? (action lovers, family etc)
   - [CTA 53-60s]: "পুরো সিনেমাটির HD প্রিন্ট, বিস্তারিত রিভিউ এবং ডাউনলোড লিংক পেয়ে যাবেন আমাদের ওয়েবসাইট movimoon.online এ।"
4. Tone: Professional, exciting, like a top YouTube movie reviewer (think Filmy Duniya). Not robotic.
5. NO English abbreviations. Write VFX as ভিএফএক্স.
6. End with invitation to visit site.

OUTPUT FORMAT: Valid JSON ONLY. No markdown.
{{
"voiceover": "Here will be 140-160 words Bengali voiceover, exactly 1 minute long...",
"caption": "Here write a VIRAL Facebook caption in Bengali: Line 1: Title with emoji 🎬🔥, Line 2: Rating + Year, Line 3: 2-line hook, Line 4: Call to action with link {link}, Line 5: 8-10 hashtags like #MoviMoon #MovieReview #NewMovie #BengaliReview #Trending. Include link compulsorily."
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
            data = {"contents":[{"parts":[{"text":prompt}]}], "generationConfig":{"temperature":0.8}}
            res = requests.post(url, json=data, timeout=45)
            if res.status_code == 200:
                text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                m = re.search(r'\{.*\}', text, re.DOTALL)
                if m:
                    j = json.loads(m.group())
                    voice = j.get("voiceover","").strip()
                    caption = j.get("caption","").strip()
                    if voice and caption:
                        if link not in caption: caption += f"\n\n👉 ফুল রিভিউ: {link}"
                        print(f"Gemini {model} OK - {len(voice.split())} words")
                        return voice, caption
            print(f"Gemini {model} failed: {res.status_code} {res.text[:300]}")
        except Exception as e:
            print(f"Gemini {model} error: {e}")
            continue
    return None, None

async def generate_tts_voice(text, output_path="voice.mp3"):
    replacements = {"VFX": "ভিএফএক্স", "AI": "এ আই", "OTT": "ওটিটি", "BGM": "বিজিএম", "CGI": "সিজিআই", "IMDb": "আইএমডিবি"}
    for en, bn in replacements.items():
        text = text.replace(en, bn)
    print(f"TTS: {len(text.split())} words - target 1min")
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

def create_9_16_hd_video(trailer_path, poster_path, voice_path, output="final.mp4"):
    """
    NEW 9:16 HD LOGIC:
    - Canvas: 1080x1920 (Full HD vertical)
    - Background: Blurred poster filling full canvas
    - Foreground: Trailer centered (16:9) on blurred background
    - Audio: trailer low + voice loud, 720p+ HD
    """
    try:
        if Path(output).exists(): Path(output).unlink()
        
        # Check if poster exists, if not use trailer blurred as background
        if poster_path and Path(poster_path).exists():
            print(f"Creating 9:16 HD with poster background: {poster_path}")
            # Use poster as blurred background
            cmd = (
                f'ffmpeg -y -loop 1 -t 60 -i "{poster_path}" '
                f'-i "{trailer_path}" -i "{voice_path}" '
                f'-filter_complex "'
                f'[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=35:steps=2,setsar=1,trim=duration=60[bg];'
                f'[1:v]scale=1080:608:force_original_aspect_ratio=decrease[fg];'
                f'[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1:format=auto,scale=1080:1920:flags=lanczos[base];'
                f'[1:a]volume=0.12[trailera];'
                f'[2:a]volume=1.0,loudnorm=I=-14:TP=-1.5:LRA=11[voicea];'
                f'[trailera][voicea]amix=inputs=2:duration=shortest:dropout_transition=0,volume=1.2[a]" '
                f'-map "[base]" -map "[a]" '
                f'-c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p -r 30 '
                f'-c:a aac -b:a 192k -shortest -t 65 "{output}"'
            )
        else:
            print("Poster not found, using trailer blurred background for 9:16")
            # Fallback: use trailer itself blurred as background
            cmd = (
                f'ffmpeg -y -i "{trailer_path}" -i "{voice_path}" '
                f'-filter_complex "'
                f'[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=25:steps=2[bg];'
                f'[0:v]scale=1080:608:force_original_aspect_ratio=decrease[fg];'
                f'[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,scale=1080:1920:flags=lanczos[base];'
                f'[0:a]volume=0.12[trailera];'
                f'[1:a]volume=1.0,loudnorm=I=-14:TP=-1.5:LRA=11[voicea];'
                f'[trailera][voicea]amix=inputs=2:duration=shortest:dropout_transition=0,volume=1.2[a]" '
                f'-map "[base]" -map "[a]" '
                f'-c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p -r 30 '
                f'-c:a aac -b:a 192k -shortest -t 65 "{output}"'
            )
        
        print(f"FFmpeg 9:16 HD cmd: {cmd[:300]}...")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=180)
        print(f"FFmpeg out: {result.stdout[-500:] if result.stdout else 'no out'}")
        print(f"FFmpeg err: {result.stderr[-800:] if result.stderr else 'no err'}")
        
        if Path(output).exists() and Path(output).stat().st_size > 50000:
            dur = get_video_duration(output)
            # Verify resolution
            probe_cmd = f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=WxH "{output}"'
            probe_res = subprocess.run(probe_cmd, shell=True, capture_output=True, text=True)
            print(f"✅ Final 9:16 HD video: {probe_res.stdout.strip()} - {dur:.1f}s - {Path(output).stat().st_size/1024/1024:.2f} MB")
            return output
        return None
    except Exception as e:
        print(f"9:16 FFmpeg Error: {e}")
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
    print("=== MAIN START - 9:16 HD MODE ===")
    history = load_history()
    print(f"History loaded: {len(history)} items")
    items = get_trending_mixed()
    print(f"Found {len(items)} recent items")
    if not items:
        print("No items found, exit")
        return
    for movie in items:
        try:
            tmdb_id = str(movie.get('id'))
            title_raw = movie.get('title') or movie.get('name') or "Unknown"
            print(f"\n>>> Processing: {title_raw} ({tmdb_id}) - 9:16 HD")
            if is_already_posted(tmdb_id, history, days=30):
                print(f"SKIPPED: {title_raw}")
                continue
            yt_url, yt_key = get_youtube_trailer(movie)
            print(f"Trailer URL: {yt_url}")
            if not yt_url:
                print(f"No trailer for {title_raw}")
                continue
            title = title_raw
            year = (movie.get("release_date") or movie.get("first_air_date") or "2025")[:4]
            rating = round(movie.get("vote_average",0), 1)
            overview = movie.get("overview","")[:600]
            link, m_type = build_movimoon_link(movie)
            voice_text, caption = call_gemini_video_script(title, year, m_type, rating, overview, link)
            if not voice_text or not caption:
                print(f"Gemini failed for {title_raw}, trying next...")
                continue
            
            # Download HD trailer (720p minimum)
            trailer_file = download_trailer(yt_url, "trailer.mp4")
            if not trailer_file:
                print(f"Download failed for {title_raw}, next...")
                continue
            
            # NEW: Download poster for blurred background
            poster_file = download_movie_poster(movie, "poster.jpg")
            
            trailer_60s = trim_trailer_to_60s(trailer_file, "trailer_60s.mp4")
            asyncio.run(generate_tts_voice(voice_text, "voice.mp3"))
            
            # NEW: Create 9:16 HD final video
            final_video = create_9_16_hd_video(trailer_60s, poster_file, "voice.mp3", "final.mp4")
            
            if not final_video or not os.path.exists(final_video):
                print("9:16 Merge failed")
                continue
            success = False
            if FB_PAGE_ID and FB_PAGE_TOKEN:
                resp = upload_video_to_facebook(FB_PAGE_ID, FB_PAGE_TOKEN, final_video, caption, "PAGE")
                if resp and resp.status_code == 200:
                    success = True
                    print("PAGE SUCCESS - 9:16 HD")
                else:
                    print(f"PAGE FAILED: {resp.text[:300] if resp else 'No response'}")
            if FB_GROUP_ID and FB_PAGE_TOKEN and success:
                try:
                    time.sleep(3)
                    resp2 = upload_video_to_facebook(FB_GROUP_ID, FB_PAGE_TOKEN, final_video, caption, "GROUP")
                    if resp2 and resp2.status_code == 200:
                        print("GROUP SUCCESS")
                    else:
                        print(f"GROUP SKIP: {resp2.text[:200] if resp2 else 'No response'}")
                except Exception as ge:
                    print(f"GROUP error (skip): {ge}")
            if success:
                history[tmdb_id] = datetime.now().isoformat()
                save_history(history)
            for f in ["trailer.mp4","trailer_60s.mp4","voice.mp3","final.mp4","poster.jpg"]:
                if os.path.exists(f):
                    try: os.remove(f)
                    except: pass
            print("Done 1 video 9:16 HD, exiting.")
            break
        except Exception as e:
            print(f"MAIN ERROR: {e}")
            import traceback
            traceback.print_exc()
            continue
    print("=== MAIN END - 9:16 HD ===")

if __name__ == "__main__":
    main()
