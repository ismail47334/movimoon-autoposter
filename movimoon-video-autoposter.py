import os, requests, random, re, time, asyncio, json, subprocess
from datetime import datetime, timedelta
import edge_tts

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
FB_GROUP_ID = os.getenv("FB_GROUP_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# === FINAL VOICE SETTING - Version 4 - MALE FAST STUDIO + SMART CUT ===
VOICE = "bn-IN-BashkarNeural"  # Male voice as requested
RATE = "+28%"   # Fast but clear studio pace
PITCH = "+2Hz"  # Slight high for energetic male
VOLUME = "+30%" # Studio loud
HISTORY_FILE = "posted_history.json"
TARGET_DURATION = 60  # 1 minute exact

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

def download_trailer(youtube_url, output="trailer.mp4"):
    try:
        if os.path.exists(output):
            os.remove(output)
        print(f"Downloading Trailer: {youtube_url}")

        cookie_arg = ""
        if os.path.exists("cookies.txt"):
            cookie_arg = '--cookies cookies.txt'
            print("\u2705 Using cookies.txt for YouTube bypass")
        else:
            print("\u26a0\ufe0f cookies.txt not found, trying without")

        # HD DOWNLOAD - 1080p priority
        clients = ["android", "ios", "mweb", "web"]
        for client in clients:
            try:
                # Best quality: 1080p, then 720p fallback
                cmd = f'yt-dlp {cookie_arg} --extractor-args "youtube:player_client={client}" --js-runtimes deno -f "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --force-ipv4 --no-warnings --extractor-retries 2'
                print(f"Trying client={client} HD 1080p {'with cookies' if cookie_arg else 'without'}")
                ret = os.system(cmd)
                if os.path.exists(output) and os.path.getsize(output) > 100000:
                    print(f"\u2705 Download Success HD with {client}")
                    return output
            except Exception as e:
                print(f"Client {client} failed: {e}")
                continue

        # Final fallback
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

def get_video_duration(video_path):
    try:
        cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{video_path}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return float(result.stdout.strip())
    except:
        return 0

def trim_trailer_to_60s(input_path, output_path="trailer_60s.mp4"):
    """
    SMART CUT - No scene miss!
    If trailer > 70s: take 6 clips x 10s = 60s from start to end spread evenly
    If 60-70s: take full
    If <60s: use full
    """
    try:
        duration = get_video_duration(input_path)
        print(f"Original Trailer Duration: {duration:.1f}s")

        if duration <= 65:
            print(f"Trailer is already ~1 min ({duration:.1f}s), using full - HD kept")
            if input_path != output_path:
                os.system(f'ffmpeg -y -i "{input_path}" -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k "{output_path}"')
                return output_path if os.path.exists(output_path) else input_path
            return input_path

        # SMART CUT LOGIC: 122s video -> 6 parts, 10s each
        # For 60s target: 6 clips * 10s
        target = 60
        num_clips = 6
        clip_dur = target // num_clips  # 10s each

        print(f"Long trailer {duration:.1f}s - Smart Cutting {num_clips} clips x {clip_dur}s = {target}s to cover all scenes")

        # Calculate spread points
        # Divide video into 6 equal sections, take 10s from each section's start
        filter_parts = []
        concat_v = ""
        concat_a = ""

        for i in range(num_clips):
            # Spread evenly: section start = i * (duration/num_clips)
            section_start = i * (duration / num_clips)
            # Take clip from middle of section for better scene coverage
            # Add small offset so we don't always start at 0 of section
            clip_start = section_start + 1  # 1s inside section
            clip_end = clip_start + clip_dur

            # Ensure we don't go beyond duration
            if clip_end > duration:
                clip_end = duration
                clip_start = max(0, clip_end - clip_dur)

            print(f"  Clip {i+1}: {clip_start:.1f}s to {clip_end:.1f}s ({clip_dur}s)")

            filter_parts.append(f"[0:v]trim=start={clip_start}:end={clip_end},setpts=PTS-STARTPTS[v{i}];")
            filter_parts.append(f"[0:a]atrim=start={clip_start}:end={clip_end},setpts=PTS-STARTPTS[a{i}];")
            concat_v += f"[v{i}]"
            concat_a += f"[a{i}]"

        filter_complex = "".join(filter_parts) + f"{concat_v}concat=n={num_clips}:v=1:a=0[vcat];{concat_a}concat=n={num_clips}:v=0:a=1[acat]"

        cmd = f'ffmpeg -y -i "{input_path}" -filter_complex "{filter_complex}" -map "[vcat]" -map "[acat]" -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k "{output_path}"'
        print(f"Running Smart Cut FFmpeg...")
        os.system(cmd)

        if os.path.exists(output_path):
            new_dur = get_video_duration(output_path)
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"\u2705 Smart Cut Done: {new_dur:.1f}s, {size:.1f} MB, 6 scenes covered - No scene miss!")
            return output_path

        print("Smart Cut failed, falling back to middle cut")
        # Fallback: middle 60s
        middle = duration / 2
        start = max(0, middle - 30)
        os.system(f'ffmpeg -y -ss {start} -i "{input_path}" -t 60 -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k "{output_path}"')
        return output_path if os.path.exists(output_path) else input_path

    except Exception as e:
        print(f"Smart Trim Error: {e}")
        import traceback
        traceback.print_exc()
        return input_path

def call_gemini_video_script(title, year, media_type, rating, overview_en, link):
    hashtag = slugify(title).replace('-','')
    prompt = f"""
You are MoviMoon.online - Bangladesh's #1 Professional Movie Reviewer & Viral Video Script Writer.

INPUT DATA:
Title: {title} ({year})
Type: {media_type} (Use 'সিনেমা' for movie, 'সিরিজ' for tv)
Rating: {rating}/10
Story Overview: {overview_en}
MoviMoon Link: {link}

=== TASK 1: 1-MINUTE VOICEOVER SCRIPT (CRITICAL - MUST BE 150-170 WORDS) ===

GOAL: Explain what happens in this movie/series in exactly 1 minute, with main attraction points.

STRUCTURE (Follow 100%):
1. Hook (15 words): "ভাই! {title} এর ট্রেইলারটা দেখলেন? সত্যি বলতে..."
2. Main Story (60 words): What is the core plot? Who is main character? What conflict? What is unique? Use 2-3 key twists without spoiler.
3. Strengths (40 words): Mention 3 strengths: অভিনয়, পরিচালনা, ভিএফএক্স/বিজিএম, গল্পের টুইস্ট, ইমোশন, অ্যাকশন কোরিওগ্রাফি - pick relevant 3.
4. For Whom + CTA (35 words): কারা দেখবে, কেন মাস্ট ওয়াচ, এক বসায় শেষ হবে কিনা, লাস্ট লাইন "ডিটেইলস, কাস্ট, ট্রেলার সব পাবেন MoviMoon এ"

TONE: Fast-paced, energetic, studio anchor style. Like professional film critic. Use words: ফার্স্ট হাফে, সেকেন্ড হাফে, ক্লাইম্যাক্স, টপ নচ, গুজবাম্প, মাস্ট ওয়াচ, এক বসায় শেষ, পয়সা উসুল

WORD COUNT: 150-170 words = 58-65 seconds at +28% male speed. MUST COUNT. Professional male anchor style, energetic.

=== TASK 2: VIRAL FB CAPTION (160-190 words) ===

Format:
Line1: 🔥 Viral Hook (1 emoji + shocking line)
Line2: {title} ({year}) | সিনেমা/সিরিজ | ⭐ {rating}/10
Line3-6: Professional review - story, acting, direction, technical
Line7: Who should watch?
Line8: Question to engage comment
Line9: CTA: 👉 ফুল রিভিউ, কাস্ট, অফিসিয়াল ট্রেলার, কোথায় দেখবেন - সব এক জায়গায়: {link}
Line10: Hashtags: #MoviMoon #TrendingNow #{hashtag} #BanglaReview #MovieLovers

=== CRITICAL TTS RULES - MUST FOLLOW 100% ===
- NEVER write English acronyms: VFX, AI, OTT, BGM, CGI, IMDb
- ALWAYS write Bangla: ভিএফএক্স, এ আই, ওটিটি, বিজিএম, সিজিআই, আইএমডিবি
- Write "ভিএফএক্স আর বিজিএম টপ নচ" NOT "VFX and BGM top notch"
- Use allowed English-Bangla mix: ফার্স্ট হাফে, সেকেন্ড হাফে, ক্লাইম্যাক্স, অ্যাকশন

OUTPUT ONLY VALID JSON:
{{"voiceover": "150-170 words Bangla script here...", "caption": "160-190 words caption here..."}}
"""
    models = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-1.5-flash"]
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
                    # Clean markdown
                    text = re.sub(r"```json|```", "", text).strip()
                    try:
                        data = json.loads(text)
                        voice = data.get("voiceover","").strip()
                        caption = data.get("caption","").strip()
                        if voice and caption:
                            word_count = len(voice.split())
                            print(f"Gemini {model} success - Voice words: {word_count}")
                            if word_count < 120:
                                print(f"Too short ({word_count} words), trying longer...")
                                continue
                            if link not in caption:
                                caption += f"\n\n\ud83d\udc49 ফুল রিভিউ, কাস্ট, ট্রেলার দেখো MoviMoon এ: {link}"
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
                                        caption += f"\n\n\ud83d\udc49 ফুল রিভিউ, কাস্ট, ট্রেলার দেখো MoviMoon এ: {link}"
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

    word_count = len(text.split())
    print(f"\ud83c\udf99\ufe0f TTS Text: {word_count} words - {text[:180]}...")
    print(f"Voice: {VOICE}, Rate: {RATE}, Volume: {VOLUME}")

    # Studio quality: Add pauses for professional feel
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH, volume=VOLUME)
    await communicate.save(output_path)

    # Apply loudnorm for studio quality
    try:
        loud_path = output_path.replace(".mp3", "_loud.mp3")
        os.system(f'ffmpeg -y -i "{output_path}" -filter:a loudnorm=I=-16:TP=-1.5:LRA=11 "{loud_path}"')
        if os.path.exists(loud_path):
            os.replace(loud_path, output_path)
            print(f"Studio loudnorm applied")
    except:
        pass

    print(f"TTS Saved: {output_path} - Target ~60s")
    return output_path

def merge_trailer_voice(trailer_path, voice_path, output="final.mp4"):
    try:
        if os.path.exists(output):
            os.remove(output)

        # Get durations
        trailer_dur = get_video_duration(trailer_path)
        voice_dur = get_video_duration(voice_path)
        print(f"Merging - Trailer: {trailer_dur:.1f}s, Voice: {voice_dur:.1f}s - Target: 60s")

        # Studio merge: trailer bg 15% volume, voice 100%, final loud, HD video keep
        # Use shortest to match voice duration, ensure 1 min video
        cmd = f'ffmpeg -y -i "{trailer_path}" -i "{voice_path}" -filter_complex "[0:a]volume=0.12[a0];[1:a]volume=1.0,loudnorm=I=-14:TP=-1.5:LRA=11,apulsator=hz=0.12[a1];[a0][a1]amix=inputs=2:duration=shortest:dropout_transition=0,volume=1.2[a]" -map 0:v -map "[a]" -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k -shortest -t 65 "{output}"'
        print("FFmpeg Merging HD Trailer + Studio Voice (1 min)...")
        os.system(cmd)

        if os.path.exists(output):
            final_dur = get_video_duration(output)
            size_mb = os.path.getsize(output) / (1024*1024)
            print(f"\u2705 Final Video: {final_dur:.1f}s, {size_mb:.1f} MB, HD 1080p")
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
                print(f"\u23ed\ufe0f SKIPPED DUPLICATE: {title_raw} (ID: {tmdb_id})")
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

            # NEW: Trim to 60s middle cut for HD 1-min video
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
                    print(f"\u2705 PAGE POST SUCCESS")

            if FB_GROUP_ID and FB_PAGE_TOKEN and page_success:
                try:
                    time.sleep(3)
                    print(f"Trying GROUP post (may fail due to FB API limits)...")
                    resp2 = upload_video_to_facebook(FB_GROUP_ID, FB_PAGE_TOKEN, final_video, caption, "GROUP VIDEO")
                    if resp2 and resp2.status_code == 200:
                        print(f"\u2705 GROUP POST SUCCESS")
                    else:
                        print(f"\u26a0\ufe0f GROUP SKIPPED - Deprecated API. Page is main. {resp2.text[:200] if resp2 else ''}")
                except Exception as e:
                    print(f"\u26a0\ufe0f Group exception (ignored): {e}")

            if success:
                history[tmdb_id] = datetime.now().isoformat()
                save_history(history)
                print(f"\u2705 Saved to history: {tmdb_id} - {title_raw}")

            for f in ["trailer.mp4","trailer_60s.mp4","voice.mp3","final.mp4"]:
                if os.path.exists(f):
                    try: os.remove(f)
                    except: pass

            print("Done 1 HD video (1 min), exiting this run.")
            break

        except Exception as e:
            print(f"MAIN LOOP ERROR for movie {movie.get('id')}: {e}")
            import traceback
            traceback.print_exc()
            continue

if __name__ == "__main__":
    main()
