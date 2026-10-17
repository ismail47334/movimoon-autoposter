import os, requests, random, re, time, asyncio, json, subprocess
from datetime import datetime, timedelta
import edge_tts

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
FB_GROUP_ID = os.getenv("FB_GROUP_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# === FINAL VOICE SETTING - Version 4 - MALE FAST STUDIO + SMART CUT + YOUR GEMINI LIST ===
VOICE = "bn-IN-BashkarNeural"  # Male voice as you requested
RATE = "+28%"   # Fast energetic male studio
PITCH = "+2Hz"
VOLUME = "+30%" # Studio loud
HISTORY_FILE = "posted_history.json"
TARGET_DURATION = 60

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
    except Exception as e:
        print(f"History Load Error: {e}")
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
    all_results = []
    urls = [
        f"https://api.themoviedb.org/3/trending/all/day?api_key={TMDB_API_KEY}&language=en-US",
        f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_original_language=hi&sort_by=popularity.desc&page=1",
        f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_original_language=bn&sort_by=popularity.desc&page=1",
        f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_original_language=te&sort_by=popularity.desc&page=1",
        f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_original_language=ta&sort_by=popularity.desc&page=1",
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=15).json()
            results = [m for m in r.get("results", []) if m.get("id")]
            for m in results:
                if 'media_type' not in m:
                    m['media_type'] = 'tv' if 'first_air_date' in m else 'movie'
            all_results.extend(results[:6])
        except Exception as e:
            print(f"TMDB Fetch Error: {e}")
            continue
    random.shuffle(all_results)
    seen = set()
    unique = []
    for m in all_results:
        if m['id'] not in seen:
            unique.append(m)
            seen.add(m['id'])
    return unique[:10]

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

def download_trailer(youtube_url, output="trailer.mp4"):
    try:
        if os.path.exists(output):
            os.remove(output)
        print(f"Downloading Trailer: {youtube_url}")

        cookie_arg = ""
        if os.path.exists("cookies.txt"):
            cookie_arg = '--cookies cookies.txt'
            print("✅ Using cookies.txt for YouTube bypass")
        else:
            print("⚠️ cookies.txt not found, trying without")

        # HD 1080p + Cookies + Deno bypass - YOUR WORKING LOGIC KEPT
        clients = ["android", "ios", "mweb", "web"]
        for client in clients:
            try:
                cmd = f'yt-dlp {cookie_arg} --extractor-args "youtube:player_client={client}" --js-runtimes deno -f "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --force-ipv4 --no-warnings --extractor-retries 2'
                print(f"Trying client={client} HD 1080p {'with cookies' if cookie_arg else 'without'}")
                os.system(cmd)
                if os.path.exists(output) and os.path.getsize(output) > 100000:
                    print(f"✅ Download Success HD with {client}")
                    return output
            except Exception as e:
                print(f"Client {client} failed: {e}")
                continue

        try:
            cmd = f'yt-dlp {cookie_arg} -f "b" -o "{output}" "{youtube_url}"'
            os.system(cmd)
            if os.path.exists(output):
                return output
        except:
            pass
        return None
    except Exception as e:
        print(f"Download Error: {e}")
        return None

def trim_trailer_to_60s(input_path, output_path="trailer_60s.mp4"):
    """
    SMART CUT - No scene miss! 5-10 sec clips spread from start to end
    122s video -> 6 clips x 10s = 60s covering all scenes
    """
    try:
        duration = get_video_duration(input_path)
        print(f"Original Trailer Duration: {duration:.1f}s")

        if duration <= 65:
            print(f"Already ~1 min ({duration:.1f}s), using full HD")
            if input_path != output_path:
                os.system(f'ffmpeg -y -i "{input_path}" -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k "{output_path}"')
                return output_path if os.path.exists(output_path) else input_path
            return input_path

        target = 60
        num_clips = 6
        clip_dur = 10

        print(f"Long trailer {duration:.1f}s - Smart Cutting {num_clips} clips x {clip_dur}s = {target}s to cover all scenes")

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

            print(f"  Clip {i+1}: {clip_start:.1f}s to {clip_end:.1f}s")

            filter_parts.append(f"[0:v]trim=start={clip_start}:end={clip_end},setpts=PTS-STARTPTS[v{i}];")
            filter_parts.append(f"[0:a]atrim=start={clip_start}:end={clip_end},setpts=PTS-STARTPTS[a{i}];")
            concat_v += f"[v{i}]"
            concat_a += f"[a{i}]"

        filter_complex = "".join(filter_parts) + f"{concat_v}concat=n={num_clips}:v=1:a=0[vcat];{concat_a}concat=n={num_clips}:v=0:a=1[acat]"

        cmd = f'ffmpeg -y -i "{input_path}" -filter_complex "{filter_complex}" -map "[vcat]" -map "[acat]" -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k "{output_path}"'
        print("Running Smart Cut FFmpeg...")
        os.system(cmd)

        if os.path.exists(output_path):
            new_dur = get_video_duration(output_path)
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Smart Cut Done: {new_dur:.1f}s, {size:.1f} MB, 6 scenes covered!")
            return output_path

        print("Smart Cut failed, fallback middle cut")
        middle = duration / 2
        start = max(0, middle - 30)
        os.system(f'ffmpeg -y -ss {start} -i "{input_path}" -t 60 -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k "{output_path}"')
        return output_path if os.path.exists(output_path) else input_path

    except Exception as e:
        print(f"Smart Trim Error: {e}")
        import traceback
        traceback.print_exc()
        return input_path

# === GEMINI - YOUR WORKING MODEL LIST KEPT EXACTLY AS YOUR LAST LOG ===
def call_gemini_video_script(title, year, media_type, rating, overview_en, link):
    hashtag = slugify(title).replace('-','')
    prompt = f"""
You are MoviMoon.online - Bangladesh's #1 Professional Movie Reviewer & Viral Video Script Writer (Male Anchor).

INPUT DATA:
Title: {title} ({year})
Type: {media_type} (Use 'সিনেমা' for movie, 'সিরিজ' for tv)
Rating: {rating}/10
Story Overview: {overview_en}
MoviMoon Link: {link}

=== TASK 1: 1-MINUTE MALE VOICEOVER SCRIPT (MUST BE 150-170 WORDS - VERY IMPORTANT) ===

You must write 150-170 words = 60 seconds at +28% speed male voice. Count words!

STRUCTURE (Professional Male Anchor, Fast Studio):
1. Hook (20 words): "ভাই! {title} এর ট্রেইলারটা দেখলেন? সত্যি বলতে..." - energetic start
2. Main Plot (70 words): What happens in movie? Main character? Conflict? Stakes? 2-3 key moments without spoiler. What makes it different?
3. Strengths (40 words): Mention 3 technical strengths: অভিনয়, পরিচালনা, ভিএফএক্স, বিজিএম, অ্যাকশন কোরিওগ্রাফি, টুইস্ট, ইমোশন - pick relevant
4. Verdict + CTA (30 words): কারা দেখবে, কেন মাস্ট ওয়াচ, এক বসায় শেষ কিনা, পয়সা উসুল কিনা, "ডিটেইলস MoviMoon এ"

TONE: Fast-paced male energetic, like professional film critic. Words: ফার্স্ট হাফে, সেকেন্ড হাফে, ক্লাইম্যাক্স, টপ নচ, গুজবাম্প, মাস্ট ওয়াচ, এক বসায় শেষ

=== TASK 2: VIRAL FB CAPTION (160-190 words) ===
Line1: 🔥 Hook with emoji
Line2: {title} ({year}) | সিনেমা/সিরিজ | ⭐ {rating}/10
Line3-6: Review - story, acting, direction, technical
Line7: Who should watch
Line8: Question for comments
Line9: 👉 ফুল রিভিউ, কাস্ট, ট্রেলার: {link}
Line10: #MoviMoon #TrendingNow #{hashtag} #BanglaReview

CRITICAL TTS RULES - MUST FOLLOW 100%:
- NEVER English acronyms: VFX, AI, OTT, BGM, CGI, IMDb
- ALWAYS Bangla: ভিএফএক্স, এ আই, ওটিটি, বিজিএম, সিজিআই, আইএমডিবি
- Example: "ভিএফএক্স আর বিজিএম টপ নচ" NOT "VFX and BGM top notch"

OUTPUT ONLY VALID JSON:
{{"voiceover": "150-170 words Bangla male script...", "caption": "160-190 words caption..."}}
"""
    # YOUR LAST WORKING MODEL LIST - EXACTLY AS YOUR LOG SHOWED SUCCESS
    models = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-flash-latest"]
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.9, "maxOutputTokens": 2000}
            }
            res = requests.post(url, json=payload, timeout=40).json()
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
                            if wc < 120:
                                print(f"Too short {wc} words, trying longer...")
                                continue
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
                                    if link not in caption:
                                        caption += f"\n\n👉 ফুল রিভিউ, কাস্ট, ট্রেলার দেখো MoviMoon এ: {link}"
                                    return voice, caption
                            except:
                                pass
            print(f"Gemini {model} failed: {str(res)[:400]}")
        except Exception as e:
            print(f"Gemini {model} error: {e}")
            continue
    return None, None

async def generate_tts_voice(text, output_path="voice.mp3"):
    replacements = {
        "VFX": "ভিএফএক্স", "vfx": "ভিএফএক্স",
        "AI": "এ আই", "API": "এপি আই",
        "OTT": "ওটিটি", "BGM": "বিজিএম",
        "CGI": "সিজিআই", "IMDb": "আইএমডিবি", "IMDB": "আইএমডিবি",
        "UI": "ইউআই"
    }
    for en, bn in replacements.items():
        text = text.replace(en, bn)

    wc = len(text.split())
    print(f"🎙️ TTS Text: {wc} words - {text[:180]}...")
    print(f"Voice: {VOICE} MALE, Rate: {RATE}, Volume: {VOLUME} - Studio")

    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH, volume=VOLUME)
    await communicate.save(output_path)

    try:
        loud_path = output_path.replace(".mp3", "_loud.mp3")
        os.system(f'ffmpeg -y -i "{output_path}" -filter:a loudnorm=I=-14:TP=-1.5:LRA=11 "{loud_path}"')
        if os.path.exists(loud_path):
            os.replace(loud_path, output_path)
            print("Studio loudnorm applied - Male Fast")
    except:
        pass

    print(f"TTS Saved: {output_path} - Target 60s Male")
    return output_path

def merge_trailer_voice(trailer_path, voice_path, output="final.mp4"):
    try:
        if os.path.exists(output):
            os.remove(output)

        trailer_dur = get_video_duration(trailer_path)
        voice_dur = get_video_duration(voice_path)
        print(f"Merging - Trailer: {trailer_dur:.1f}s, Voice: {voice_dur:.1f}s - Target 60s HD")

        cmd = f'ffmpeg -y -i "{trailer_path}" -i "{voice_path}" -filter_complex "[0:a]volume=0.12[a0];[1:a]volume=1.0,loudnorm=I=-14:TP=-1.5:LRA=11[a1];[a0][a1]amix=inputs=2:duration=shortest:dropout_transition=0,volume=1.2[a]" -map 0:v -map "[a]" -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k -shortest -t 65 "{output}"'
        print("FFmpeg Merging HD Smart Cut + Male Studio Voice...")
        os.system(cmd)

        if os.path.exists(output):
            final_dur = get_video_duration(output)
            size_mb = os.path.getsize(output) / (1024*1024)
            print(f"✅ Final Video: {final_dur:.1f}s, {size_mb:.1f} MB, HD 1080p, 6 scenes, Male Voice")
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
            print(f"{label} {page_id}: {r.status_code} {r.text[:800]}")
            return r
    except Exception as e:
        print(f"FB Upload Error ({label}): {e}")
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
    print(f"Found {len(items)} mixed items")

    for movie in items:
        try:
            tmdb_id = str(movie.get('id'))
            title_raw = movie.get('title') or movie.get('name') or "Unknown"

            if is_already_posted(tmdb_id, history, days=30):
                print(f"⏭️ SKIPPED DUPLICATE: {title_raw} (ID: {tmdb_id})")
                continue

            yt_url, yt_key = get_youtube_trailer(movie)
            if not yt_url:
                print(f"No trailer for {title_raw} (ID {tmdb_id}), skipping")
                continue

            title = title_raw
            year = (movie.get("release_date") or movie.get("first_air_date") or "2025")[:4]
            rating = round(movie.get("vote_average",0), 1)
            overview = movie.get("overview","")[:600]
            link, m_type = build_movimoon_link(movie)

            voice_text, caption = call_gemini_video_script(title, year, m_type, rating, overview, link)
            if not voice_text or not caption:
                print(f"Gemini failed for {title_raw}, skipping")
                continue

            trailer_file = download_trailer(yt_url, "trailer.mp4")
            if not trailer_file:
                print(f"Trailer download failed for {title_raw}")
                continue

            trailer_60s = trim_trailer_to_60s(trailer_file, "trailer_60s.mp4")

            asyncio.run(generate_tts_voice(voice_text, "voice.mp3"))

            final_video = merge_trailer_voice(trailer_60s, "voice.mp3", "final.mp4")
            if not final_video or not os.path.exists(final_video):
                print("FFmpeg merge failed")
                continue

            success = False
            page_success = False

            if FB_PAGE_ID and FB_PAGE_TOKEN:
                resp = upload_video_to_facebook(FB_PAGE_ID, FB_PAGE_TOKEN, final_video, caption, "PAGE VIDEO")
                if resp and resp.status_code == 200:
                    success = True
                    page_success = True
                    print("✅ PAGE POST SUCCESS")

            if FB_GROUP_ID and FB_PAGE_TOKEN and page_success:
                try:
                    time.sleep(3)
                    print("Trying GROUP post...")
                    resp2 = upload_video_to_facebook(FB_GROUP_ID, FB_PAGE_TOKEN, final_video, caption, "GROUP VIDEO")
                    if resp2 and resp2.status_code == 200:
                        print("✅ GROUP POST SUCCESS")
                    else:
                        print(f"⚠️ GROUP SKIPPED - Deprecated API. {resp2.text[:200] if resp2 else ''}")
                except Exception as e:
                    print(f"⚠️ Group exception (ignored): {e}")

            if success:
                history[tmdb_id] = datetime.now().isoformat()
                save_history(history)
                print(f"✅ Saved to history: {tmdb_id} - {title_raw}")

            for f in ["trailer.mp4","trailer_60s.mp4","voice.mp3","final.mp4"]:
                if os.path.exists(f):
                    try: os.remove(f)
                    except: pass

            print("Done 1 HD SMART CUT Male video, exiting.")
            break

        except Exception as e:
            print(f"MAIN LOOP ERROR for movie {movie.get('id')}: {e}")
            import traceback
            traceback.print_exc()
            continue

if __name__ == "__main__":
    main()
