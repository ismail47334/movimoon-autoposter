
import os, requests, random, re, json, subprocess
from datetime import datetime, timedelta
from pathlib import Path

print("=== MoviMoon Movie Picks AutoPoster V2 - Watermark Image + Icons + CTA ===")

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN") or os.getenv("FB_ACCESS_TOKEN")

HISTORY_FILE = "picks_history.json"
WATERMARK_FILE = "watermark.png"

GEMINI_OK = False
client = None
try:
    from google import genai
    if GEMINI_API_KEY:
        client = genai.Client(api_key=GEMINI_API_KEY)
        GEMINI_OK = True
        print("Gemini NEW SDK OK")
except Exception as e:
    print(f"Gemini NEW fail {e}")
    try:
        import google.generativeai as genai_old
        genai_old.configure(api_key=GEMINI_API_KEY)
        gemini_model_old = genai_old.GenerativeModel("gemini-1.5-flash")
        GEMINI_OK = True
        print("Gemini OLD fallback OK")
    except Exception as e2:
        print(f"Both fail {e2}")

MICRO_GENRES = {
    "arctic_horror": {"title": "Arctic Horror", "genres": [27,53], "desc": "Frozen fear. Isolated terror. No escape from the cold."},
    "psychological_crime": {"title": "Psychological Crime Thrillers", "genres": [80,53,9648], "desc": "Twisted minds. Dark secrets. Every clue hides a lie."},
    "time_travel_sci_fi": {"title": "Time Travel Sci-Fi", "genres": [878,53,9648], "desc": "Time bends. Reality breaks. Past and future collide."},
    "survival_action": {"title": "Survival Action", "genres": [28,12,53], "desc": "One mistake. No second chance. Survive at any cost."},
    "dream_realities": {"title": "Dream Connections & Hidden Realities", "genres": [14,27,878], "desc": "Dreams bleed into reality. What is real anymore?"},
    "serial_killer": {"title": "Serial Killer Crime Thrillers", "genres": [80,53,27], "desc": "Hunting a monster. Every murder is a message."},
    "found_footage_horror": {"title": "Found Footage Horror", "genres": [27,9648], "desc": "They pressed record. Evil answered back."},
    "interdimensional_portals": {"title": "Interdimensional Portals & Otherworldly Threats", "genres": [878,27,14], "desc": "A door opens. Something comes through."},
    "tactical_action": {"title": "Tactical Action", "genres": [28,10752,80], "desc": "One team. One mission. No room for error."},
    "racing_action": {"title": "Racing & High-Octane Action", "genres": [28,12], "desc": "Full throttle. No brakes. Race or die."}
}

INDUSTRY_CONFIG = {
    "hollywood": {"lang": "en", "desc": "Hollywood"},
    "bollywood": {"lang": "hi", "desc": "Bollywood"},
    "south": {"lang": "te,ta,ml,kn", "desc": "South Indian"},
    "series": {"lang": "en", "desc": "Series", "media": "tv"},
}

TIME_SLOTS = {
    "morning": {"bd_time": "সকাল ৮টা", "pool": ["tactical_action","survival_action","racing_action"], "industries": ["hollywood","bollywood","south"]},
    "afternoon": {"bd_time": "দুপুর ২টা", "pool": ["psychological_crime","time_travel_sci_fi","serial_killer"], "industries": ["hollywood","bollywood","south","series"]},
    "night": {"bd_time": "রাত ৯টা", "pool": ["arctic_horror","found_footage_horror","interdimensional_portals","dream_realities"], "industries": ["hollywood","bollywood","series"]}
}

def get_current_slot():
    h = datetime.utcnow().hour
    if 1 <= h <= 4: return "morning"
    elif 7 <= h <= 10: return "afternoon"
    else: return "night"

def load_history():
    try:
        if Path(HISTORY_FILE).exists():
            return json.loads(Path(HISTORY_FILE).read_text(encoding='utf-8'))
    except: pass
    return {}

def save_history(h):
    Path(HISTORY_FILE).write_text(json.dumps(h, indent=2), encoding='utf-8')

def is_posted(tmdb_id, history, days=30):
    tmdb_id = str(tmdb_id)
    if tmdb_id not in history: return False
    try:
        last = datetime.fromisoformat(history[tmdb_id])
        return datetime.now() - last < timedelta(days=days)
    except: return False

def fetch_tmdb_movies_micro(micro_key, industry_key, count=9):
    cfg = MICRO_GENRES[micro_key]
    ind_cfg = INDUSTRY_CONFIG[industry_key]
    genre_ids = cfg["genres"]
    is_tv = ind_cfg.get("media") == "tv"
    base = "https://api.themoviedb.org/3"
    mtype = "tv" if is_tv else "movie"
    min_year = datetime.now().year - 15
    genre_str = ",".join(map(str, genre_ids))
    urls = []
    if is_tv:
        urls.append(f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_genres={genre_str}&first_air_date.gte={min_year}-01-01&sort_by=popularity.desc&vote_count.gte=50&page=1")
    else:
        if industry_key == "hollywood":
            urls.append(f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_genres={genre_str}&primary_release_date.gte={min_year}-01-01&sort_by=popularity.desc&vote_count.gte=100&with_original_language=en&page=1")
        elif industry_key == "bollywood":
            urls.append(f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_genres={genre_str}&primary_release_date.gte={min_year}-01-01&sort_by=popularity.desc&vote_count.gte=20&with_original_language=hi&page=1")
        elif industry_key == "south":
            for l in ["te","ta","ml","kn"]:
                urls.append(f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_genres={genre_str}&primary_release_date.gte={min_year}-01-01&sort_by=popularity.desc&with_original_language={l}&page=1")
    urls.append(f"{base}/trending/{mtype}/week?api_key={TMDB_API_KEY}")
    all_results = []
    for url in urls:
        try:
            r = requests.get(url, timeout=15).json()
            for m in r.get("results", []):
                if not m.get("poster_path"): continue
                m['media_type'] = mtype
                all_results.append(m)
        except: continue
    seen=set(); unique=[]
    for m in all_results:
        if m['id'] not in seen and m.get("popularity",0) >=5:
            unique.append(m); seen.add(m['id'])
    random.shuffle(unique)
    print(f"Fetched {len(unique)} for {micro_key} - {industry_key}")
    return unique[:count]

def download_posters(movies):
    files=[]
    for idx,m in enumerate(movies):
        try:
            url = f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}"
            data = requests.get(url, timeout=20).content
            fname = f"poster_{idx}.jpg"
            Path(fname).write_bytes(data)
            files.append(fname)
            print(f"Downloaded {idx+1}: {m.get('title') or m.get('name')}")
        except Exception as e:
            print(f"Fail {e}")
    return files

def create_916_grid_with_image_watermark(image_files, watermark_path="watermark.png", output_file="merged_post.jpg"):
    count=len(image_files)
    if count<6: return None
    while len(image_files)<9: image_files.append(image_files[-1])
    inputs=[]
    for img in image_files[:9]: inputs.extend(["-i", img])
    has_wm = Path(watermark_path).exists()
    if has_wm:
        inputs.extend(["-i", watermark_path])
        print(f"Watermark OK {Path(watermark_path).stat().st_size} bytes")
    parts=[]
    for i in range(9): parts.append(f"[{i}:v]scale=360:640:force_original_aspect_ratio=increase,crop=360:640[v{i}];")
    layout="0_0|360_0|720_0|0_640|360_640|720_640|0_1280|360_1280|720_1280"
    xstack=f"[v0][v1][v2][v3][v4][v5][v6][v7][v8]xstack=inputs=9:layout={layout}[grid];"
    if has_wm:
        filt="".join(parts)+xstack+"[9:v]scale=900:-1:flags=lanczos[wm];[grid][wm]overlay=(W-w)/2:(H-h)/2:format=auto[out]"
    else:
        font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        filt="".join(parts)+xstack+f"[grid]drawbox=x=(w-750)/2:y=(h-110)/2:w=750:h=110:color=black@0.65:t=fill,drawtext=text='watch on movimoon.online':fontfile={font}:fontcolor=white:fontsize=36:x=(w-text_w)/2:y=(h-text_h)/2[out]"
    cmd=["ffmpeg","-y"]+inputs+["-filter_complex",filt,"-map","[out]","-frames:v","1","-q:v","2",output_file]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True)
        print(f"Collage {output_file} {Path(output_file).stat().st_size/1024:.1f}KB")
        return output_file
    except Exception as e:
        print(f"Collage err {e}")
        return None

def generate_caption_gemini(movies, micro_cfg, industry_cfg):
    movie_data=[{"name": m.get("title") or m.get("name"), "year": (m.get("release_date") or m.get("first_air_date") or "2023")[:4], "rating": round(m.get("vote_average",7.0),1), "overview": m.get("overview","")[:200], "type": micro_cfg['title']} for m in movies]
    prompt=f"""You are MoviMoon curator. Theme: {micro_cfg['title']} - {industry_cfg['desc']}

EXACT FORMAT WITH ICONS:

🍿 MoviMoon Movie Picks: {micro_cfg['title']}

{micro_cfg['desc']}

🎬 1. Movie Name (Year)
⭐ IMDb Rating: X.X/10
📺 OTT Platform: Check MoviMoon.Online
🎭 Movie Type: {micro_cfg['title']}
📅 Release Year: Year
💡 Highlight: [2 sentences in BENGALI/Bangla]

... same for 9

👉 দুর্দান্ত সব মুভি/সিরিজ দেখতে বা ডাউনলোড করতে এখনি গুগলে সার্চ করুন বা সরাসরি ভিজিট করুন MoviMoon.Online ।

Hashtags:
#MovieName #MoviMoon

RULES: Each line must start with icon as above. Highlight Bengali 2 sentences. OTT always Check MoviMoon.Online. After 9 movies add CTA line exactly.

Data: {json.dumps(movie_data, ensure_ascii=False)}
"""
    text_result=""
    if client and GEMINI_OK:
        try:
            for model_name in ["gemini-3.5-flash-lite","gemini-3.8-flash"]:
                try:
                    resp = client.models.generate_content(model=model_name, contents=prompt)
                    text_result = resp.text
                    print(f"Gemini {model_name} OK {len(text_result)}")
                    break
                except Exception as me:
                    print(f"Model {model_name} fail {me}")
                    continue
        except Exception as e:
            print(f"Gemini err {e}")
    if not text_result and 'gemini_model_old' in globals():
        try:
            resp = gemini_model_old.generate_content(prompt)
            text_result = resp.text
        except Exception as e:
            print(f"OLD fail {e}")
    if not text_result:
        lines=[f"🍿 MoviMoon Movie Picks: {micro_cfg['title']}", "", micro_cfg['desc'], ""]
        for i,m in enumerate(movie_data,1):
            lines.append(f"🎬 {i}. {m['name']} ({m['year']})")
            lines.append(f"⭐ IMDb Rating: {m['rating']}/10")
            lines.append(f"📺 OTT Platform: Check MoviMoon.Online")
            lines.append(f"🎭 Movie Type: {micro_cfg['title']}")
            lines.append(f"📅 Release Year: {m['year']}")
            lines.append(f"💡 Highlight: একটি অসাধারণ গল্প যা আপনাকে মুগ্ধ করবে। শেষ পর্যন্ত টানটান উত্তেজনা থাকবে।")
            lines.append("")
        lines.append("👉 দুর্দান্ত সব মুভি/সিরিজ দেখতে বা ডাউনলোড করতে এখনি গুগলে সার্চ করুন বা সরাসরি ভিজিট করুন MoviMoon.Online ।")
        lines.append("")
        lines.append("Hashtags: #MoviMoon")
        text_result="\n".join(lines)
    text_result = re.sub(r"📺 OTT Platform:.*", "📺 OTT Platform: Check MoviMoon.Online", text_result, flags=re.IGNORECASE)
    text_result = re.sub(r"OTT Platform:.*", "📺 OTT Platform: Check MoviMoon.Online", text_result, flags=re.IGNORECASE)
    cta="👉 দুর্দান্ত সব মুভি/সিরিজ দেখতে বা ডাউনলোড করতে এখনি গুগলে সার্চ করুন বা সরাসরি ভিজিট করুন MoviMoon.Online ।"
    if cta not in text_result:
        if "Hashtags:" in text_result:
            text_result = text_result.replace("Hashtags:", f"{cta}\n\nHashtags:")
        else:
            text_result+=f"\n\n{cta}"
    return text_result

def post_to_facebook(image_path, caption):
    if not FB_PAGE_ID or not FB_PAGE_TOKEN: return None
    url=f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
    payload={'caption': caption, 'access_token': FB_PAGE_TOKEN}
    try:
        with open(image_path,'rb') as img:
            r=requests.post(url, data=payload, files={'source': img}, timeout=60)
            data=r.json()
            print(f"FB {data}")
            return data if 'id' in data or 'post_id' in data else None
    except Exception as e:
        print(f"FB err {e}")
        return None

def main():
    slot=get_current_slot()
    slot_cfg=TIME_SLOTS[slot]
    print(f"Slot {slot} Pool {slot_cfg['pool']}")
    micro_key=random.choice(slot_cfg['pool'])
    industry_key=random.choice(slot_cfg['industries'])
    micro_cfg=MICRO_GENRES[micro_key]
    industry_cfg=INDUSTRY_CONFIG[industry_key]
    print(f"Selected {micro_cfg['title']} {industry_cfg['desc']}")
    history=load_history()
    movies=fetch_tmdb_movies_micro(micro_key, industry_key, 9)
    fresh=[m for m in movies if not is_posted(m['id'], history, 30)]
    if len(fresh)<6: fresh=movies
    fresh=fresh[:9]
    if len(fresh)<6: print("Not enough"); return
    posters=download_posters(fresh)
    if len(posters)<6: print("Poster fail"); return
    collage=create_916_grid_with_image_watermark(posters, WATERMARK_FILE, "merged_post.jpg")
    if not collage: return
    caption=generate_caption_gemini(fresh, micro_cfg, industry_cfg)
    print(f"Caption {caption[:500]}...")
    fb=post_to_facebook(collage, caption)
    if fb:
        print(f"✅ SUCCESS {fb.get('id')}")
        for m in fresh: history[str(m['id'])]=datetime.now().isoformat()
        save_history(history)
    for f in posters+[collage]:
        try: Path(f).unlink()
        except: pass

if __name__=="__main__": main()
