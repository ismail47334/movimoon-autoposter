import os, requests, random, re, time, asyncio, json, subprocess, pathlib
from datetime import datetime, timedelta
from pathlib import Path

print("=== MoviMoon Bot - V40 FINAL | YOUR WORKING TTS + Fixed FFmpeg ===")

try:
    import edge_tts
    print("edge_tts OK")
except Exception as e:
    print(f"edge_tts fail {e}")
    import sys; sys.exit(1)

from google import genai
from google.genai import types

# ENV
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
FB_GROUP_ID = os.getenv("FB_GROUP_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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
    except: pass
    return {}

def save_history(history):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"History Save Error: {e}")

def is_already_posted(tmdb_id, history, days=30):
    tmdb_id = str(tmdb_id)
    if tmdb_id not in history: return False
    try:
        last_date = datetime.fromisoformat(history[tmdb_id])
        if datetime.now() - last_date < timedelta(days=days):
            return True
    except: return False
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
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=15).json()
            results = [m for m in r.get("results", []) if m.get("id")]
            for m in results:
                if 'media_type' not in m:
                    m['media_type'] = 'tv' if 'first_air_date' in m else 'movie'
            all_results.extend(results[:10])
        except: continue
    filtered = []
    for m in all_results:
        try:
            date_str = m.get("release_date") or m.get("first_air_date") or ""
            if not date_str: continue
            year = int(date_str[:4])
            if year >= min_year:
                filtered.append(m)
        except: continue
    random.shuffle(filtered)
    seen = set(); unique = []
    for m in filtered:
        if m['id'] not in seen:
            unique.append(m); seen.add(m['id'])
    return unique[:10]

def get_youtube_trailer(movie):
    tmdb_id = movie['id']
    m_type = movie.get('media_type','movie')
    if m_type not in ['movie','tv']: m_type = 'movie'
    url = f"https://api.themoviedb.org/3/{m_type}/{tmdb_id}/videos?api_key={TMDB_API_KEY}&language=en-US"
    try:
        r = requests.get(url, timeout=10).json()
        results = r.get('results', [])
        def is_valid(v):
            if v.get('site') != 'YouTube': return False
            if v.get('type','').lower() not in ['trailer','teaser']: return False
            name = v.get('name','').lower()
            block = ['muhurat','making','behind','interview','clip','song','lyrical','motion poster']
            for kw in block:
                if kw in name: return False
            return True
        valid = [v for v in results if is_valid(v)]
        valid_sorted = sorted(valid, key=lambda v: (0 if v.get('type')=='Trailer' else 1, 0 if v.get('official') else 1))
        if valid_sorted:
            v = valid_sorted[0]
            return f"https://www.youtube.com/watch?v={v['key']}", v['key']
        return None, None
    except: return None, None

def get_video_duration(video_path):
    try:
        cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{video_path}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return float(result.stdout.strip())
    except: return 0

def parse_proxy_line(line):
    line=line.strip()
    if not line or line.startswith("#"): return None
    if line.startswith("http://") or line.startswith("https://"): return line
    parts=line.split(":")
    if len(parts)==4:
        ip,port,user,pwd=parts
        return f"http://{user}:{pwd}@{ip}:{port}"
    elif len(parts)==2:
        return f"http://{line}"
    return None

def get_residential_proxies():
    proxies=[]
    proxy_list_raw=os.getenv("YOUTUBE_PROXY_LIST","")
    single_proxy=os.getenv("YOUTUBE_PROXY","")
    if proxy_list_raw:
        for line in proxy_list_raw.strip().splitlines():
            p=parse_proxy_line(line)
            if p and p not in proxies: proxies.append(p)
    if single_proxy:
        sp=parse_proxy_line(single_proxy)
        if sp and sp not in proxies:
            proxies.insert(0,sp)
    return proxies

def download_via_ytdlp_fixed(youtube_url, output="trailer.mp4"):
    print(f"=== YT-DLP V40 {youtube_url} ===")
    Path(output).unlink(missing_ok=True)
    if Path("cookies.txt").exists() and Path("cookies.txt").stat().st_size < 200:
        Path("cookies.txt").unlink(missing_ok=True)
    strategies=[
        '--js-runtimes node --remote-components ejs:github --extractor-args "youtube:player_client=tv_downgraded,android_vr,web_embedded,mweb" -f "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best" --merge-output-format mp4',
        '--js-runtimes node --extractor-args "youtube:player_client=tv,android_vr,web_embedded,mweb" -f "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best" --merge-output-format mp4',
    ]
    for strat in strategies:
        cmd=f'yt-dlp {strat} -o "{output}" "{youtube_url}" --no-playlist --no-warnings --retries 3 2>&1'
        try:
            result=subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=180)
            if Path(output).exists() and Path(output).stat().st_size>50000:
                print(f"SUCCESS {Path(output).stat().st_size/1024/1024:.2f} MB")
                return output
        except: continue
        Path(output).unlink(missing_ok=True)
    proxies=get_residential_proxies()
    for proxy in proxies[:10]:
        safe=proxy.replace('"','')
        for strat in strategies[:1]:
            cmd=f'yt-dlp --proxy "{safe}" {strat} -o "{output}" "{youtube_url}" --no-playlist --retries 2 --socket-timeout 30 2>&1'
            try:
                subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=120)
                if Path(output).exists() and Path(output).stat().st_size>50000:
                    return output
            except: continue
            Path(output).unlink(missing_ok=True)
    return None

def download_movie_poster(movie, output="poster.jpg"):
    try:
        poster_path=movie.get("poster_path")
        if not poster_path: return None
        url=f"https://image.tmdb.org/t/p/original{poster_path}"
        r=requests.get(url,timeout=20)
        if r.status_code==200:
            with open(output,'wb') as f: f.write(r.content)
            return output
    except: pass
    return None

def get_genre_names(genre_ids):
    genre_map={28:"Action",12:"Adventure",16:"Animation",35:"Comedy",80:"Crime",99:"Documentary",18:"Drama",10751:"Family",14:"Fantasy",36:"History",27:"Horror",10402:"Music",9648:"Mystery",10749:"Romance",878:"Sci-Fi",10770:"TV Movie",53:"Thriller",10752:"War",37:"Western",10759:"Action",10765:"Sci-Fi"}
    if not genre_ids: return "Drama, Thriller"
    names=[genre_map.get(g,"") for g in genre_ids[:3] if g in genre_map]
    return ", ".join(names) if names else "Drama, Thriller"

def generate_local_cinematic_bgm(output="bgm.mp3", category="cinematic", duration=60):
    try:
        Path(output).unlink(missing_ok=True)
        duration=int(duration)
        cmd=f'ffmpeg -y -f lavfi -i "sine=frequency=55:duration={duration},aecho=0.8:0.88:60:0.4,volume=0.35" -f lavfi -i "sine=frequency=110:duration={duration},aecho=0.8:0.9:120:0.3,volume=0.28" -filter_complex "[0:a][1:a]amix=inputs=2,volume=0.45,loudnorm=I=-16" -c:a libmp3lame -q:a 3 "{output}"'
        subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=30)
        if Path(output).exists() and Path(output).stat().st_size>1000:
            return output
    except: pass
    return None

def ensure_bgm(output="bgm.mp3", movie=None, duration=60):
    return generate_local_cinematic_bgm(output, "cinematic", duration=duration)

def smart_trim_trailer_to_60s(input_path, output_path="trailer_60s.mp4"):
    try:
        if not Path(input_path).exists(): return input_path
        dur=get_video_duration(input_path)
        if dur<=62: return input_path
        Path(output_path).unlink(missing_ok=True)
        target=60.0
        num_cuts=10 if dur<=120 else 12
        cut_dur=6.0 if dur<=120 else 5.0
        interval=(dur-cut_dur)/(num_cuts-1) if num_cuts>1 else 0
        cuts=[(round(i*interval,2), round(i*interval+cut_dur,2)) for i in range(num_cuts)]
        seg_files=[]
        for i,(s,e) in enumerate(cuts):
            seg_path=f"seg_{i}.mp4"
            cmd=f'ffmpeg -y -ss {s} -to {e} -i "{input_path}" -c:v libx264 -preset veryfast -crf 23 -c:a aac -r 30 "{seg_path}"'
            subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=90)
            if Path(seg_path).exists() and Path(seg_path).stat().st_size>10000:
                seg_files.append(seg_path)
        if len(seg_files)>=3:
            with open("concat_v40.txt","w",encoding='utf-8') as f:
                for sf in seg_files: f.write(f"file '{sf}'\n")
            cmd_concat=f'ffmpeg -y -f concat -safe 0 -i concat_v40.txt -c:v libx264 -preset veryfast -crf 23 -c:a aac "{output_path}"'
            subprocess.run(cmd_concat,shell=True,capture_output=True,text=True,timeout=120)
            for sf in seg_files:
                if Path(sf).exists(): Path(sf).unlink(missing_ok=True)
            if Path("concat_v40.txt").exists(): Path("concat_v40.txt").unlink(missing_ok=True)
            if Path(output_path).exists() and Path(output_path).stat().st_size>50000:
                return output_path
        cmd2=f'ffmpeg -y -ss 2 -i "{input_path}" -t 60 -c:v libx264 -preset veryfast -crf 23 -c:a aac "{output_path}"'
        subprocess.run(cmd2,shell=True,capture_output=True,text=True,timeout=90)
        if Path(output_path).exists(): return output_path
        return input_path
    except: return input_path

def call_gemini_video_script(title, year, m_type, rating, overview, link, movie=None, target_words=160, trailer_duration=60):
    genre_str=get_genre_names(movie.get("genre_ids",[]) if movie else [])
    title_raw=title
    if not GEMINI_API_KEY:
        voice=f"বন্ধুরা আজকে কথা বলবো {year} সালের সিনেমা {title_raw} নিয়ে।"
        story_bn="এক অসাধারণ গল্পের জগত!"
        return voice, story_bn, title_raw
    if trailer_duration<5: trailer_duration=60
    if target_words is None or target_words==0:
        target_words=int(trailer_duration*2.66)
        target_words=max(75,min(170,target_words))
    prompt=f"""Title: {title} Year: {year} Type: {m_type} Genre: {genre_str} Rating: {rating}/10 Synopsis: {overview} Link: {link} Words: {target_words}
ROLE: Bengali Movie Reviewer. Create hook + premise no spoiler + CTA "পুরো সিনেমাটি দেখতে ভিজিট করুন মুভিমুন ডট অনলাইন।"
OUTPUT JSON ONLY: {{"voiceover": "...", "bangla_title": "title", "caption": "summary"}}"""
    models=["gemini-2.0-flash","gemini-2.0-flash-lite","gemini-1.5-flash-latest"]
    for model in models:
        try:
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            data={"contents":[{"parts":[{"text":prompt}]}], "generationConfig":{"temperature":0.7,"maxOutputTokens":2048,"response_mime_type":"application/json"}}
            res=requests.post(url,json=data,timeout=30)
            if res.status_code==200:
                js=res.json()
                try:
                    text=js["candidates"][0]["content"]["parts"][0]["text"]
                    clean=text.replace("```json","").replace("```","").strip()
                    import re as re2
                    m=re2.search(r'\{.*\}',clean,re2.DOTALL)
                    if m:
                        j=json.loads(m.group())
                        voice=j.get("voiceover","").strip()
                        story_bn=j.get("caption","").strip() or "এক অসাধারণ গল্পের জগত!"
                        return voice, story_bn, j.get("bangla_title",title_raw)
                except: continue
        except: continue
    voice=f"বন্ধুরা আজকে {year} সালের {title_raw} নিয়ে কথা বলবো। {overview[:200]} পুরো সিনেমাটি দেখতে ভিজিট করুন মুভিমুন ডট অনলাইন।"
    return voice, "এক অসাধারণ গল্পের জগত!", title_raw

def build_caption(title, year, m_type, genre_str, rating, story_bn, link):
    type_label="Series" if m_type=="tv" else "Movie"
    caption=f"🎬 {type_label} - {title}({year})\n🎭 Genres - {genre_str}\n⭐ Rating - {rating}/10\n📖 Story - {story_bn}\n🔗 ফুল মুভি লিংক: {link}\n👉 পুরো রিভিউ এবং ডাউনলোড পেতে ভিজিট করুন movimoon.online\n#MoviMoon #MovieReview #TrendingNow"
    return caption

# ===== YOUR 100% WORKING TTS CODE INTEGRATED HERE - V40 =====
def generate_tts_with_gemini(text, output_path="voice.mp3"):
    """
    YOUR TESTED CODE - gemini-3.8-flash-tts
    """
    print(f"Gemini TTS V40: Generating {len(text.split())} words with Fenrir voice...")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY পাওয়া যায়নি! GitHub Secrets চেক করুন।")
    
    client = genai.Client(api_key=api_key)

    # --- এটাই মেইন ফিক্স তোমার code থেকে ---
    speech_config = types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name="Fenrir" 
            )
        )
    )

    print("ডিজাইন করা ভয়েসে বাংলা অডিও জেনারেট হচ্ছে... gemini-3.8-flash-tts")
    
    try:
        # নভেম্বর ২০২৬ এর লেটেস্ট ফ্রি মডেল - gemini-3.8-flash-tts
        response = client.models.generate_content(
            model="gemini-3.8-flash-tts",
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=speech_config
            )
        )

        # সঠিক ভাবে audio data বের করা - তোমার code
        audio_data = response.candidates[0].content.parts[0].inline_data.data

        with open(output_path, "wb") as f:
            f.write(audio_data)

        if Path(output_path).exists() and Path(output_path).stat().st_size > 1000:
            print(f"সফলভাবে অডিও তৈরি হয়েছে এবং '{output_path}' এ সেভ হয়েছে! {Path(output_path).stat().st_size/1024:.1f} KB")
            return True
        else:
            print("Audio file too small")
            return False
    except Exception as e:
        print(f"Gemini TTS FAILED V40: {e}")
        import traceback
        traceback.print_exc()
        return False

async def generate_tts_voice(text, output_path="voice.mp3"):
    print(f"TTS: {len(text.split())} words - Trying YOUR WORKING Gemini TTS first")
    gemini_success = generate_tts_with_gemini(text, output_path)
    if gemini_success:
        print(f"Using YOUR WORKING Gemini TTS SUCCESS - Fenrir")
        try:
            studio_path=output_path.replace(".mp3","_studio.mp3")
            cmd=f'ffmpeg -y -i "{output_path}" -filter:a "loudnorm=I=-16:TP=-1.5:LRA=7,volume=1.05" -c:a libmp3lame -q:a 0 -ar 48000 "{studio_path}"'
            subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=20)
            if Path(studio_path).exists() and Path(studio_path).stat().st_size>1000:
                Path(studio_path).replace(output_path)
        except: pass
        return output_path
    
    print(f"Gemini TTS failed, FALLBACK to Edge TTS")
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH, volume=VOLUME)
    await communicate.save(output_path)
    return output_path

def sanitize_drawtext(text):
    if not text: return "Movie"
    text=str(text)
    text=text.replace("'"," ").replace('"'," ").replace(":"," ").replace("\n"," ").replace("\r"," ")
    text=" ".join(text.split())
    if len(text)>45: text=text[:42]+"..."
    return text.strip() or "Movie"

def create_9_16_hd_video(trailer_path, poster_path, voice_path, output="final.mp4", bgm_path=None, trailer_duration=60, title_text="MoviMoon", m_type="movie"):
    try:
        if Path(output).exists(): Path(output).unlink()
        has_bgm=bgm_path and Path(bgm_path).exists()
        if not has_bgm:
            bgm_path=generate_local_cinematic_bgm("bgm.mp3","cinematic",duration=trailer_duration)
        dur=int(trailer_duration)
        safe_title=sanitize_drawtext(title_text)
        label_top="Movie Name" if m_type=="movie" else "Series Name"
        label_top_safe=sanitize_drawtext(label_top)
        font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if not Path(font_path).exists():
            font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        print(f"Creating {dur}s video V40 FIXED FFmpeg - Top: {label_top_safe} | {safe_title}")
        
        if poster_path and Path(poster_path).exists():
            filter_complex = (
                f"[0:v]scale=1440:2560:force_original_aspect_ratio=increase,crop=1440:2560,gblur=sigma=25:steps=2,setsar=1,trim=duration={dur}[bg];"
                f"[1:v]scale=1440:1664:force_original_aspect_ratio=increase,crop=1440:1664,setsar=1[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=0,scale=1440:2560:flags=lanczos[base];"
                f"[base]drawtext=text='{label_top_safe}':fontcolor=white:fontsize=50:box=1:boxcolor=black@0.70:boxborderw=13:borderw=2:bordercolor=black:"
                f"x=(w-text_w)/2:y=90+4*sin(t*1.8):shadowcolor=black:shadowx=4:shadowy=4:fontfile={font_path}[t1];"
                f"[t1]drawtext=text='{safe_title}':fontcolor=white:fontsize=82:box=1:boxcolor=black@0.75:boxborderw=18:borderw=4:bordercolor=black:"
                f"x=(w-text_w)/2:y=160+5*sin(t*1.8):shadowcolor=black:shadowx=5:shadowy=5:fontfile={font_path}[t2];"
                f"[t2]drawtext=text='Watch on':fontcolor=white:fontsize=48:box=1:boxcolor=black@0.70:boxborderw=13:borderw=2:bordercolor=black:"
                f"x=(w-text_w)/2:y=h-260-4*sin(t*2.2):shadowcolor=black:shadowx=4:shadowy=4:fontfile={font_path}[t3];"
                f"[t3]drawtext=text='movimoon.online':fontcolor=yellow:fontsize=70:box=1:boxcolor=black@0.75:boxborderw=18:borderw=4:bordercolor=black:"
                f"x=(w-text_w)/2:y=h-190-5*sin(t*2.2):shadowcolor=black:shadowx=4:shadowy=4:fontfile={font_path}[final_v];"
                f"[1:a]volume=0.30[trailer_low];[3:a]volume=0.40[bg_vol];[2:a]asplit=2[voice_sc][voice_mix];"
                f"[bg_vol][voice_sc]sidechaincompress=threshold=0.015:ratio=8:attack=20:release=400:makeup=1[ducked];"
                f"[trailer_low][ducked][voice_mix]amix=inputs=3:duration=longest:dropout_transition=0:weights=0.30 0.35 1,volume=1.25,loudnorm=I=-16:TP=-1.5:LRA=8[a]"
            )
            cmd = (
                f'ffmpeg -y -loop 1 -t {dur} -i "{poster_path}" -i "{trailer_path}" -i "{voice_path}" -stream_loop -1 -i "{bgm_path}" '
                f'-filter_complex "{filter_complex}" '
                f'-map "[final_v]" -map "[a]" -c:v libx264 -profile:v high -level:v 4.2 -preset fast -crf 20 -pix_fmt yuv420p -r 30 -movflags +faststart -c:a aac -b:a 192k -t {dur} "{output}"'
            )
        else:
            filter_complex = (
                f"[0:v]scale=1440:2560:force_original_aspect_ratio=increase,crop=1440:2560,gblur=sigma=25:steps=2[bg];"
                f"[0:v]scale=1440:1664:force_original_aspect_ratio=increase,crop=1440:1664[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,scale=1440:2560:flags=lanczos[base];"
                f"[base]drawtext=text='{label_top_safe}':fontcolor=white:fontsize=50:box=1:boxcolor=black@0.70:boxborderw=13:borderw=2:bordercolor=black:"
                f"x=(w-text_w)/2:y=90+4*sin(t*1.8):shadowcolor=black:shadowx=4:shadowy=4:fontfile={font_path}[t1];"
                f"[t1]drawtext=text='{safe_title}':fontcolor=white:fontsize=82:box=1:boxcolor=black@0.75:boxborderw=18:borderw=4:bordercolor=black:"
                f"x=(w-text_w)/2:y=160+5*sin(t*1.8):shadowcolor=black:shadowx=5:shadowy=5:fontfile={font_path}[t2];"
                f"[t2]drawtext=text='Watch on':fontcolor=white:fontsize=48:box=1:boxcolor=black@0.70:boxborderw=13:borderw=2:bordercolor=black:"
                f"x=(w-text_w)/2:y=h-260-4*sin(t*2.2):shadowcolor=black:shadowx=4:shadowy=4:fontfile={font_path}[t3];"
                f"[t3]drawtext=text='movimoon.online':fontcolor=yellow:fontsize=70:box=1:boxcolor=black@0.75:boxborderw=18:borderw=4:bordercolor=black:"
                f"x=(w-text_w)/2:y=h-190-5*sin(t*2.2):shadowcolor=black:shadowx=4:shadowy=4:fontfile={font_path}[final_v];"
                f"[0:a]volume=0.30[trailer_low];[2:a]volume=0.40[bg_vol];[1:a]asplit=2[voice_sc][voice_mix];"
                f"[bg_vol][voice_sc]sidechaincompress=threshold=0.015:ratio=8:attack=20:release=400:makeup=1[ducked];"
                f"[trailer_low][ducked][voice_mix]amix=inputs=3:duration=longest:dropout_transition=0:weights=0.30 0.35 1,volume=1.25,loudnorm=I=-16:TP=-1.5:LRA=8[a]"
            )
            cmd = (
                f'ffmpeg -y -i "{trailer_path}" -i "{voice_path}" -stream_loop -1 -i "{bgm_path}" '
                f'-filter_complex "{filter_complex}" '
                f'-map "[final_v]" -map "[a]" -c:v libx264 -profile:v high -level:v 4.2 -preset fast -crf 20 -pix_fmt yuv420p -r 30 -movflags +faststart -c:a aac -b:a 192k -t {dur} "{output}"'
            )
        print(f"FFmpeg V40 FIXED {dur}s running...")
        result=subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=600)
        if Path(output).exists() and Path(output).stat().st_size>50000:
            print(f"Final OK V40 {Path(output).stat().st_size/1024/1024:.2f} MB")
            return output
        print(f"FFmpeg err {result.stderr[-1500:]}")
        return None
    except Exception as e:
        print(f"V40 Video Error {e}")
        import traceback; traceback.print_exc()
        return None

def upload_video_to_facebook(page_id, token, video_path, caption, label):
    try:
        print(f"Uploading {label} - {Path(video_path).stat().st_size/1024/1024:.2f} MB")
        url=f"https://graph.facebook.com/v18.0/{page_id}/videos"
        with open(video_path,'rb') as f:
            files={'source':f}
            data={'description':caption,'access_token':token}
            r=requests.post(url,files=files,data=data,timeout=300)
            print(f"FB Upload {label} Status {r.status_code} {r.text[:500]}")
            if r.status_code==200:
                return r.json()
        return None
    except Exception as e:
        print(f"FB Upload Error {e}")
        return None

async def main():
    print("=== MoviMoon AutoPoster V40 FINAL START ===")
    history=load_history()
    movies=get_trending_mixed()
    if not movies:
        print("No movies found"); return
    for idx,movie in enumerate(movies[:10],1):
        try:
            tmdb_id=str(movie['id'])
            if is_already_posted(tmdb_id,history):
                print(f"[{idx}/10] Already posted {tmdb_id}, skipping"); continue
            title=movie.get('title') or movie.get('name') or 'Unknown'
            title_raw=title
            print(f">>> [{idx}/10] {title} ({tmdb_id})")
            date_str=movie.get('release_date') or movie.get('first_air_date') or ''
            year=date_str[:4] if date_str else str(datetime.now().year)
            m_type=movie.get('media_type','movie')
            rating=movie.get('vote_average',7.0)
            overview=movie.get('overview','') or 'An extraordinary story.'
            genre_str=get_genre_names(movie.get('genre_ids',[]))
            link=f"https://movimoon.online/movie/{tmdb_id}-{slugify(title)}" if m_type=='movie' else f"https://movimoon.online/tv/{tmdb_id}-{slugify(title)}"
            youtube_url,yt_key=get_youtube_trailer(movie)
            if not youtube_url:
                print(f"No trailer for {title}, skipping"); continue
            trailer_file=download_via_ytdlp_fixed(youtube_url,"trailer.mp4")
            if not trailer_file:
                print(f"Trailer download failed for {title}"); continue
            poster_file=download_movie_poster(movie,"poster.jpg")
            trailer_dur_raw=get_video_duration(trailer_file)
            estimated_final=min(trailer_dur_raw,60.0)
            target_words=int(estimated_final*2.66)
            target_words=max(75,min(160,target_words))
            voice_text,story_bn,bangla_title=call_gemini_video_script(title,year,m_type,rating,overview,link,movie,target_words=target_words,trailer_duration=trailer_dur_raw)
            wc=len(voice_text.split())
            if wc>target_words:
                voice_text=" ".join(voice_text.split()[:target_words])
            caption=build_caption(title,year,m_type,genre_str,rating,story_bn,link)
            await generate_tts_voice(voice_text,"voice.mp3")
            trailer_60s=smart_trim_trailer_to_60s(trailer_file,"trailer_60s.mp4")
            trailer_dur=get_video_duration(trailer_60s)
            bgm_file=ensure_bgm("bgm.mp3",movie,duration=int(trailer_dur))
            final_video=create_9_16_hd_video(trailer_60s,poster_file,"voice.mp3","final.mp4",bgm_path=bgm_file,trailer_duration=int(trailer_dur),title_text=title_raw,m_type=m_type)
            if not final_video or not Path(final_video).exists():
                print(f"Final video creation failed for {title}"); continue
            fb_result=upload_video_to_facebook(FB_PAGE_ID,FB_PAGE_TOKEN,final_video,caption,title)
            if fb_result:
                print(f"✅ PAGE POSTED SUCCESSFULLY - ID: {fb_result.get('id','unknown')}")
                history[tmdb_id]=datetime.now().isoformat()
                save_history(history)
                print(f"Posted {title} successfully - WORK DONE")
                for f in ["trailer.mp4","trailer_60s.mp4","poster.jpg","voice.mp3","bgm.mp3","final.mp4"]:
                    try:
                        if Path(f).exists(): Path(f).unlink()
                    except: pass
                print(f"🎉 1 VIDEO DONE - STOPPING")
                break
            else:
                print(f"Failed to post {title}")
            for f in ["trailer.mp4","trailer_60s.mp4","poster.jpg","voice.mp3","bgm.mp3","final.mp4"]:
                try:
                    if Path(f).exists(): Path(f).unlink()
                except: pass
            await asyncio.sleep(10)
        except Exception as e:
            print(f"Error {e}")
            import traceback; traceback.print_exc()
            continue
    print("=== V40 END ===")

if __name__=="__main__":
    asyncio.run(main())
