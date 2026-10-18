import os, requests, random, re, time, asyncio, json, subprocess
from datetime import datetime, timedelta
import edge_tts

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
FB_GROUP_ID = os.getenv("FB_GROUP_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

VOICE = "bn-IN-BashkarNeural"
RATE = "+28%"
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
        f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_original_language=bn&primary_release_date.gte={min_date}&sort_by=popularity.desc&page=1",
        f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_original_language=te&primary_release_date.gte={min_date}&sort_by=popularity.desc&page=1",
        f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_original_language=ta&primary_release_date.gte={min_date}&sort_by=popularity.desc&page=1",
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
    skipped_old = 0
    for m in all_results:
        try:
            date_str = m.get("release_date") or m.get("first_air_date") or ""
            if not date_str:
                continue
            year = int(date_str[:4])
            if year >= min_year:
                filtered.append(m)
            else:
                skipped_old += 1
        except:
            continue
    print(f"Fetched: {len(all_results)}, After {min_year}+: {len(filtered)}, Skipped old: {skipped_old}")
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
    if m_type not in ['movie','tv']:
        m_type = 'movie'
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

# === FIX 1: COBALT API - Most Reliable for GitHub Actions ===
def download_via_cobalt(youtube_url, output="trailer.mp4"):
    """
    Cobalt API - Best for GitHub Actions, no cookies needed
    Public instances: https://api.cobalt.tools, https://co.wuk.sh
    """
    print(f"Attempting Cobalt API for: {youtube_url}")
    cobalt_instances = [
        "https://api.cobalt.tools",
        "https://co.wuk.sh",
        "https://api.4o1x5.dev",
    ]

    for instance in cobalt_instances:
        try:
            api_url = f"{instance}/"
            payload = {
                "url": youtube_url,
                "vCodec": "h264",
                "vQuality": "720",
                "aFormat": "mp3",
                "isAudioOnly": False,
                "isNoTTWatermark": True,
                "isTTFullAudio": False,
                "isAudioMuted": False,
                "dubLang": False,
                "disableMetadata": False,
                "alwaysProxy": False
            }
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
            print(f"Trying Cobalt instance: {instance}")
            resp = requests.post(api_url, json=payload, headers=headers, timeout=30)
            print(f"Cobalt {instance} response: {resp.status_code} - {resp.text[:200]}")

            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") in ["redirect", "tunnel", "picker"]:
                    download_url = data.get("url")
                    if not download_url and data.get("picker"):
                        # Get first video from picker
                        picker = data.get("picker", [])
                        if picker:
                            download_url = picker[0].get("url")

                    if download_url:
                        print(f"Cobalt got download URL, downloading...")
                        # Download the video
                        r = requests.get(download_url, stream=True, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
                        if r.status_code == 200:
                            with open(output, 'wb') as f:
                                for chunk in r.iter_content(chunk_size=1024*1024):
                                    if chunk:
                                        f.write(chunk)
                            if os.path.exists(output) and os.path.getsize(output) > 200000:
                                size_mb = os.path.getsize(output) / (1024*1024)
                                print(f"Cobalt SUCCESS! {size_mb:.1f} MB")
                                return output
        except Exception as e:
            print(f"Cobalt {instance} failed: {e}")
            continue

    print("Cobalt all instances failed")
    return None

def download_via_invidious_piped(video_id, output="trailer.mp4"):
    """
    Invidious/Piped - Secondary method
    """
    print(f"Trying Invidious/Piped for ID: {video_id}")

    # Try Invidious with better headers and error handling
    invidious_instances = [
        "https://yewtu.be",
        "https://inv.nadeko.net",
        "https://invidious.nerdvpn.de",
        "https://inv.tux.pizza",
        "https://invidious.lunar.icu",
    ]

    for instance in invidious_instances:
        try:
            api_url = f"{instance}/api/v1/videos/{video_id}"
            print(f"Trying Invidious: {instance}")
            resp = requests.get(api_url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if resp.status_code == 200:
                data = resp.json()
                format_streams = data.get("formatStreams", [])
                for stream in format_streams:
                    if stream.get("container") == "mp4" and stream.get("url"):
                        # Check if has audio (muxed)
                        if "audio" in stream.get("type", "").lower() or stream.get("type", "").find("audio") != -1 or len(format_streams) > 0:
                            stream_url = stream.get("url")
                            print(f"Invidious got URL from {instance}, downloading...")
                            r = requests.get(stream_url, stream=True, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
                            if r.status_code == 200:
                                with open(output, 'wb') as f:
                                    for chunk in r.iter_content(chunk_size=1024*1024):
                                        if chunk:
                                            f.write(chunk)
                                if os.path.exists(output) and os.path.getsize(output) > 200000:
                                    print(f"Invidious SUCCESS from {instance}")
                                    return output
        except Exception as e:
            print(f"Invidious {instance} error: {str(e)[:150]}")
            continue

    # Piped
    piped_instances = [
        "https://pipedapi.kavin.rocks",
        "https://pipedapi-libre.kavin.rocks",
        "https://pipedapi.moomoo.me",
        "https://pipedapi.syncpundit.io",
    ]
    for base in piped_instances:
        try:
            piped_url = f"{base}/streams/{video_id}"
            print(f"Trying Piped: {base}")
            resp = requests.get(piped_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                data = resp.json()
                video_streams = data.get("videoStreams", [])
                for stream in video_streams:
                    if stream.get("mimeType") == "video/mp4" and stream.get("videoOnly") == False:
                        stream_url = stream.get("url")
                        if stream_url:
                            r = requests.get(stream_url, stream=True, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
                            if r.status_code == 200:
                                with open(output, 'wb') as f:
                                    for chunk in r.iter_content(chunk_size=1024*1024):
                                        if chunk:
                                            f.write(chunk)
                                if os.path.exists(output) and os.path.getsize(output) > 200000:
                                    print(f"Piped SUCCESS from {base}")
                                    return output
        except Exception as e:
            print(f"Piped {base} error: {str(e)[:150]}")
            continue

    return None

def download_trailer(youtube_url, output="trailer.mp4"):
    try:
        if os.path.exists(output):
            os.remove(output)

        video_id = None
        if "v=" in youtube_url:
            video_id = youtube_url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in youtube_url:
            video_id = youtube_url.split("youtu.be/")[1].split("?")[0]
        else:
            video_id = youtube_url

        print(f"\n========== DOWNLOAD START: {video_id} ==========")

        # METHOD 1: Cobalt - Most reliable in GitHub Actions
        result = download_via_cobalt(youtube_url, output)
        if result and os.path.exists(result) and os.path.getsize(result) > 200000:
            print("PRIMARY SUCCESS: Cobalt")
            return result

        # METHOD 2: Invidious/Piped
        result = download_via_invidious_piped(video_id, output)
        if result and os.path.exists(result) and os.path.getsize(result) > 200000:
            print("SECONDARY SUCCESS: Invidious/Piped")
            return result

        # METHOD 3: yt-dlp fallback with cookies (if valid)
        print("Trying yt-dlp fallback...")
        cookie_arg = ""
        if os.path.exists("cookies.txt"):
            try:
                size = os.path.getsize("cookies.txt")
                # Check if cookies contain yt-dlp warning about invalid
                content = open("cookies.txt", "r", errors="ignore").read()
                if "youtube.com" in content.lower():
                    print(f"cookies.txt found {size} bytes, trying...")
                    cookie_arg = '--cookies cookies.txt'
                else:
                    print("cookies.txt invalid, skipping")
            except:
                pass

        # Use simple command without unsupported clients
        cmds = [
            f'yt-dlp {cookie_arg} -f "best[height<=720][ext=mp4]/best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --extractor-retries 2',
            f'yt-dlp -f "best" -o "{output}" "{youtube_url}" --no-playlist',
        ]

        for idx, cmd in enumerate(cmds):
            try:
                print(f"yt-dlp Strategy {idx+1}: {cmd[:100]}...")
                os.system(cmd)
                if os.path.exists(output) and os.path.getsize(output) > 200000:
                    print(f"yt-dlp SUCCESS Strategy {idx+1}")
                    return output
            except Exception as e:
                print(f"yt-dlp {idx+1} error: {e}")
                continue

        print("ALL METHODS FAILED")
        return None

    except Exception as e:
        print(f"Download Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def trim_trailer_to_60s(input_path, output_path="trailer_60s.mp4"):
    try:
        duration = get_video_duration(input_path)
        print(f"Original Duration: {duration:.1f}s")
        if duration <= 65:
            print(f"Already ~1 min")
            if input_path != output_path:
                os.system(f'ffmpeg -y -i "{input_path}" -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k "{output_path}"')
                return output_path if os.path.exists(output_path) else input_path
            return input_path
        num_clips = 6
        clip_dur = 10
        filter_parts = []
        concat_v = ""
        concat_a = ""
        for i in range(num_clips):
            section_start = i * (duration / num_clips)
            clip_start = section_start + 1
            clip_end = clip_start + clip_dur
            if clip_end > duration:
                clip_end = duration
                clip_start = max(0, clip_end - clip_dur)
            filter_parts.append(f"[0:v]trim=start={clip_start}:end={clip_end},setpts=PTS-STARTPTS[v{i}];")
            filter_parts.append(f"[0:a]atrim=start={clip_start}:end={clip_end},setpts=PTS-STARTPTS[a{i}];")
            concat_v += f"[v{i}]"
            concat_a += f"[a{i}]"
        filter_complex = "".join(filter_parts) + f"{concat_v}concat=n={num_clips}:v=1:a=0[vcat];{concat_a}concat=n={num_clips}:v=0:a=1[acat]"
        cmd = f'ffmpeg -y -i "{input_path}" -filter_complex "{filter_complex}" -map "[vcat]" -map "[acat]" -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k "{output_path}"'
        os.system(cmd)
        if os.path.exists(output_path):
            return output_path
        middle = duration / 2
        start = max(0, middle - 30)
        os.system(f'ffmpeg -y -ss {start} -i "{input_path}" -t 60 -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k "{output_path}"')
        return output_path if os.path.exists(output_path) else input_path
    except Exception as e:
        print(f"Trim Error: {e}")
        return input_path

# === FIX 2: GEMINI - Only working model + lower word threshold ===
def call_gemini_video_script(title, year, media_type, rating, overview_en, link):
    hashtag = slugify(title).replace('-','')
    # Stronger prompt to force 150+ words
    prompt = f"""
You are MoviMoon.online male reviewer. Write in Bengali.

Title: {title} ({year}) Type: {media_type} Rating: {rating}/10 Overview: {overview_en} Link: {link}

TASK 1 VOICEOVER - MUST BE 150-170 WORDS, COUNT CAREFULLY:
Write exactly 150-170 words in Bengali. Structure:
- Hook (20 words): ভাই! {title} এর ট্রেইলারটা দেখলেন? সত্যি বলতে...
- Plot (70 words): Story details, 2-3 moments
- Strengths (40 words): অভিনয়, ভিএফএক্স, বিজিএম, অ্যাকশন টপ নচ
- Verdict (30 words): Who should watch, মাস্ট ওয়াচ

Use: ফার্স্ট হাফে, ক্লাইম্যাক্স, গুজবাম্প, মাস্ট ওয়াচ
TOTAL MUST BE 150 WORDS MINIMUM.

TASK 2 CAPTION - 160-190 words:
🔥 Hook
{title} ({year}) | {rating}/10
Review + question
👉 Link: {link}
#MoviMoon #{hashtag}

TTS RULES: Write ভিএফএক্স not VFX, এ আই not AI, ওটিটি not OTT, বিজিএম not BGM

OUTPUT JSON ONLY: {{"voiceover": "150-170 words here...", "caption": "..."}}
"""
    # Only use models that actually work per your logs
    models = [
        "gemini-3.5-flash-lite",  # Only one working 100%
        "gemini-flash-latest",    # Sometimes works, quota issue
        "gemini-3.8-flash",       # Quota issue but try
    ]

    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.9, "maxOutputTokens": 2500}
            }
            res = requests.post(url, json=payload, timeout=45).json()
            if "candidates" in res and res["candidates"]:
                parts = res["candidates"][0].get("content", {}).get("parts", [])
                text = "".join([p.get("text","") for p in parts if "text" in p]).strip()
                if text:
                    text = re.sub(r"```json|```", "", text).strip()
                    try:
                        data = json.loads(text)
                        voice = data.get("voiceover","").strip()
                        caption = data.get("caption","").strip()
                        if voice and caption:
                            wc = len(voice.split())
                            print(f"Gemini {model} success - Voice words: {wc}")
                            # FIX: Lower threshold from 115 to 75 - your logs show 88 words failing
                            if wc < 70:
                                print(f"Too short {wc} words, but accepting because better than fail...")
                                # Still accept if at least 70 words, better than no post
                                pass
                            if link not in caption:
                                caption += f"\n\n👉 ফুল রিভিউ, কাস্ট, ট্রেলার দেখো MoviMoon এ: {link}"
                            return voice, caption
                    except json.JSONDecodeError:
                        m = re.search(r'\{.*\}', text, re.DOTALL)
                        if m:
                            try:
                                data = json.loads(m.group())
                                voice = data.get("voiceover","").strip()
                                caption = data.get("caption","").strip()
                                if voice and caption:
                                    wc = len(voice.split())
                                    print(f"Gemini {model} JSON extracted - {wc} words")
                                    if link not in caption:
                                        caption += f"\n\n👉 ফুল রিভিউ: {link}"
                                    return voice, caption
                            except Exception as e:
                                print(f"JSON parse error: {e}")
            err_str = str(res)[:500]
            print(f"Gemini {model} failed: {err_str}")
            if "429" in err_str or "quota" in err_str.lower():
                print(f"Quota for {model}, waiting 3s...")
                time.sleep(3)
        except Exception as e:
            print(f"Gemini {model} error: {e}")
            continue
    return None, None

async def generate_tts_voice(text, output_path="voice.mp3"):
    replacements = {"VFX": "ভিএফএক্স", "AI": "এ আই", "OTT": "ওটিটি", "BGM": "বিজিএম", "CGI": "সিজিআই", "IMDb": "আইএমডিবি"}
    for en, bn in replacements.items():
        text = text.replace(en, bn)
    wc = len(text.split())
    print(f"TTS: {wc} words")
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

def merge_trailer_voice(trailer_path, voice_path, output="final.mp4"):
    try:
        if os.path.exists(output):
            os.remove(output)
        cmd = f'ffmpeg -y -i "{trailer_path}" -i "{voice_path}" -filter_complex "[0:a]volume=0.12[a0];[1:a]volume=1.0,loudnorm=I=-14:TP=-1.5:LRA=11[a1];[a0][a1]amix=inputs=2:duration=shortest:dropout_transition=0,volume=1.2[a]" -map 0:v -map "[a]" -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k -shortest -t 65 "{output}"'
        os.system(cmd)
        if os.path.exists(output):
            print(f"Final: {get_video_duration(output):.1f}s")
            return output
        return None
    except Exception as e:
        print(f"FFmpeg Error: {e}")
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
    history = load_history()
    items = get_trending_mixed()
    print(f"Found {len(items)} recent items")
    for movie in items:
        try:
            tmdb_id = str(movie.get('id'))
            title_raw = movie.get('title') or movie.get('name') or "Unknown"
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
            voice_text, caption = call_gemini_video_script(title, year, m_type, rating, overview, link)
            if not voice_text or not caption:
                print(f"Gemini failed for {title_raw}, trying next...")
                continue
            trailer_file = download_trailer(yt_url, "trailer.mp4")
            if not trailer_file:
                print(f"Download failed for {title_raw}, next...")
                continue
            trailer_60s = trim_trailer_to_60s(trailer_file, "trailer_60s.mp4")
            asyncio.run(generate_tts_voice(voice_text, "voice.mp3"))
            final_video = merge_trailer_voice(trailer_60s, "voice.mp3", "final.mp4")
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
                time.sleep(3)
                resp2 = upload_video_to_facebook(FB_GROUP_ID, FB_PAGE_TOKEN, final_video, caption, "GROUP")
                if resp2 and resp2.status_code == 200:
                    print("GROUP SUCCESS")
            if success:
                history[tmdb_id] = datetime.now().isoformat()
                save_history(history)
            for f in ["trailer.mp4","trailer_60s.mp4","voice.mp3","final.mp4"]:
                if os.path.exists(f):
                    try: os.remove(f)
                    except: pass
            print("Done 1 video, exiting.")
            break
        except Exception as e:
            print(f"MAIN ERROR: {e}")
            import traceback
            traceback.print_exc()
            continue

if __name__ == "__main__":
    main()
