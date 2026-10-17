import os, requests, random, re, time, asyncio, json, subprocess
from datetime import datetime, timedelta
import edge_tts

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
FB_GROUP_ID = os.getenv("FB_GROUP_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# === FINAL VOICE SETTING - Version 2 ===
VOICE = "bn-IN-BashkarNeural"
RATE = "+10%"
PITCH = "+2Hz"
VOLUME = "+10%"
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
        # Priority: Trailer
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
        
        print(f"Downloading Trailer (Bypass Mode): {youtube_url}")
        
        # === YOUTUBE BOT BYPASS LOGIC - 3 Client Try করবে ===
        clients = [
            "android",  # সবচেয়ে Powerful Bypass
            "ios",
            "mweb"
        ]
        
        for client in clients:
            try:
                # Deno + Android Client = Bot Check Bypass
                cmd = f'yt-dlp --extractor-args "youtube:player_client={client}" --js-runtimes deno -f "mp4[height<=720][ext=mp4]/best[height<=720]" -o "{output}" "{youtube_url}" --no-playlist --merge-output-format mp4 --force-ipv4 --no-warnings'
                print(f"Trying with client: {client}")
                ret = os.system(cmd)
                if os.path.exists(output) and os.path.getsize(output) > 100000: # 100KB এর বেশি হলে Success
                    print(f"✅ Download Success with {client}")
                    return output
            except Exception as e:
                print(f"Client {client} failed: {e}")
                continue
        
        # Last Try: Piped API Fallback (YouTube Proxy)
        try:
            print("Trying Piped Fallback...")
            video_id = youtube_url.split("v=")[-1].split("&")[0]
            # Piped API দিয়ে Direct Link
            cmd = f'yt-dlp --extractor-args "youtube:player_client=android" -f "best" -o "{output}" "https://www.youtube.com/watch?v={video_id}"'
            os.system(cmd)
            if os.path.exists(output):
                return output
        except:
            pass
            
        return None
        
    except Exception as e:
        print(f"Download Error: {e}")
        return None

# === GEMINI - EXACT SAME MODEL LIST + ERROR HANDLING AS YOUR CURRENT CODE ===
def call_gemini_video_script(title, year, media_type, rating, overview_en, link):
    hashtag = slugify(title).replace('-','')
    prompt = f"""
You are MoviMoon.online Senior Movie Reviewer + Voiceover Script Writer.

INPUT:
Title: {title} ({year})
Type: {media_type} - Use 'সিনেমা' for movie, 'সিরিজ' for tv
Rating: {rating}/10
Overview: {overview_en}
MoviMoon Link: {link}

TASK 1 - VOICEOVER SCRIPT (for Edge-TTS, 90-110 words):
Start with "ভাই! {title} এর ট্রেইলারটা দেখলেন?". Natural Bengali friend style. Use words like ফার্স্ট হাফে, অ্যাকশন, টপ নচ, মাস্ট ওয়াচ, এক বসায় শেষ. Must mention 1 strength (অভিনয়/ভিএফএক্স/গল্প) + 1 honest limitation.

TASK 2 - FB CAPTION (130-170 words):
Viral hook with 1 emoji, second line: {title} ({year}) | TYPE | Rating, then review, who should watch, question, CTA with exact link, hashtags #MoviMoon #TrendingNow #{hashtag} #BanglaReview. NEVER say Free streaming.

CRITICAL TTS RULE - MUST FOLLOW 100% FOR VOICEOVER SCRIPT:
- NEVER write English acronyms like VFX, AI, API, OTT, BGM, CGI, IMDb, UI
- ALWAYS write Bangla phonetic: ভিএফএক্স, এ আই, এপি আই, ওটিটি, বিজিএম, সিজিআই, আইএমডিবি, ইউআই
- Example: Write "ভিএফএক্স আর বিজিএম টপ নচ" NOT "VFX and BGM top notch"
- Keep allowed words ফার্স্ট হাফে, অ্যাকশন, টপ নচ, মাস্ট ওয়াচ in Bangla script.

OUTPUT ONLY VALID JSON:
{{"voiceover": "Bangla script here...", "caption": "Bangla caption here..."}}
"""
    models = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-flash-latest"]
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.95, "maxOutputTokens": 1200}
            }
            res = requests.post(url, json=payload, timeout=35).json()
            if "candidates" in res and res["candidates"]:
                parts = res["candidates"][0].get("content", {}).get("parts", [])
                text = "".join([p.get("text","") for p in parts if "text" in p]).strip()
                if text:
                    # Remove markdown code blocks
                    text = re.sub(r'^```json\s*', '', text)
                    text = re.sub(r'^```\s*', '', text)
                    text = re.sub(r'\s*```$', '', text)
                    text = text.strip()
                    print(f"Gemini success with {model}")
                    try:
                        data = json.loads(text)
                        voice = data.get("voiceover","").strip()
                        caption = data.get("caption","").strip()
                        if voice and caption:
                            if link not in caption:
                                caption += f"\n\n👉 ফুল রিভিউ, কাস্ট, ট্রেলার দেখো MoviMoon এ: {link}"
                            return voice, caption
                    except json.JSONDecodeError:
                        # Try extract JSON with regex
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
    # Extra safety cleaning for TTS
    replacements = {
        "VFX": "ভিএফএক্স", "vfx": "ভিএফএক্স",
        "AI": "এ আই", "API": "এপি আই",
        "OTT": "ওটিটি", "BGM": "বিজিএম",
        "CGI": "সিজিআই", "IMDb": "আইএমডিবি", "IMDB": "আইএমডিবি"
    }
    for en, bn in replacements.items():
        text = text.replace(en, bn)
    print(f"🎙️ TTS Text: {text[:150]}...")
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH, volume=VOLUME)
    await communicate.save(output_path)
    print(f"TTS Saved: {output_path}")
    return output_path

def merge_trailer_voice(trailer_path, voice_path, output="final.mp4"):
    try:
        if os.path.exists(output):
            os.remove(output)
        # Lower trailer audio to 20%, voice 100%, mix, shortest duration
        cmd = f'ffmpeg -y -i "{trailer_path}" -i "{voice_path}" -filter_complex "[0:a]volume=0.2[a0];[1:a]volume=1.0[a1];[a0][a1]amix=inputs=2:duration=shortest:dropout_transition=2[a]" -map 0:v -map "[a]" -c:v copy -shortest "{output}"'
        print("FFmpeg Merging Trailer + Voice...")
        os.system(cmd)
        return output if os.path.exists(output) else None
    except Exception as e:
        print(f"FFmpeg Error: {e}")
        return None

def upload_video_to_facebook(page_id, token, video_path, caption, label):
    try:
        url = f"https://graph.facebook.com/v19.0/{page_id}/videos"
        with open(video_path, 'rb') as f:
            files = {'source': f}
            data = {'description': caption, 'access_token': token}
            r = requests.post(url, files=files, data=data, timeout=180)
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
    print(f"Found {len(items)} mixed items (Hollywood/Bollywood/Tollywood/South)")

    for movie in items:
        try:
            tmdb_id = str(movie.get('id'))
            title_raw = movie.get('title') or movie.get('name') or "Unknown"

            # Duplicate Check - 30 Days
            if is_already_posted(tmdb_id, history, days=30):
                print(f"⏭️ SKIPPED DUPLICATE: {title_raw} (ID: {tmdb_id}) - Already posted within 30 days")
                continue

            yt_url, yt_key = get_youtube_trailer(movie)
            if not yt_url:
                print(f"No trailer for {title_raw} (ID {tmdb_id}), skipping")
                continue

            title = title_raw
            year = (movie.get("release_date") or movie.get("first_air_date") or "2025")[:4]
            rating = round(movie.get("vote_average",0), 1)
            overview = movie.get("overview","")[:400]
            link, m_type = build_movimoon_link(movie)

            voice_text, caption = call_gemini_video_script(title, year, m_type, rating, overview, link)
            if not voice_text or not caption:
                print(f"Gemini failed for {title_raw}, skipping")
                continue

            trailer_file = download_trailer(yt_url, "trailer.mp4")
            if not trailer_file:
                print(f"Trailer download failed for {title_raw}")
                continue

            asyncio.run(generate_tts_voice(voice_text, "voice.mp3"))

            final_video = merge_trailer_voice("trailer.mp4", "voice.mp3", "final.mp4")
            if not final_video or not os.path.exists(final_video):
                print("FFmpeg merge failed")
                continue

            # Upload to Page + Group
            success = False
            if FB_PAGE_ID and FB_PAGE_TOKEN:
                resp = upload_video_to_facebook(FB_PAGE_ID, FB_PAGE_TOKEN, final_video, caption, "PAGE VIDEO")
                if resp and resp.status_code == 200:
                    success = True

            if FB_GROUP_ID and FB_PAGE_TOKEN:
                time.sleep(5)
                resp2 = upload_video_to_facebook(FB_GROUP_ID, FB_PAGE_TOKEN, final_video, caption, "GROUP VIDEO")
                if resp2 and resp2.status_code == 200:
                    success = True

            # Save to history only if at least one upload success
            if success:
                history[tmdb_id] = datetime.now().isoformat()
                save_history(history)
                print(f"✅ Saved to history: {tmdb_id} - {title_raw}")

            # Cleanup
            for f in ["trailer.mp4","voice.mp3","final.mp4"]:
                if os.path.exists(f):
                    try: os.remove(f)
                    except: pass

            # Video heavy, so 1 post per run
            print("Done 1 video, exiting this run.")
            break

        except Exception as e:
            print(f"MAIN LOOP ERROR for movie {movie.get('id')}: {e}")
            continue

if __name__ == "__main__":
    main()
