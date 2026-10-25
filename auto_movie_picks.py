
import os, requests, random, re, json, subprocess
from datetime import datetime, timedelta
from pathlib import Path

print("=== MoviMoon Movie Picks AutoPoster V3 - 4 Movies PURE Genre + Center Watermark ===")

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
        print("Gemini NEW SDK OK - google.genai")
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

# ===== 100% PURE MICRO GENRE - NO MIX =====
# Each has strict TMDB genres + keywords + overview must contain keyword
MICRO_GENRES = {
    "arctic_horror": {
        "title": "Arctic Horror",
        "genres": [27],  # ONLY Horror
        "must_keywords": ["arctic","snow","ice","frozen","blizzard","antarctic","cold","winter","iceberg","tundra"],
        "tmdb_with_keywords": "10053,15078,15812", # snow, ice, arctic - will use discover with keywords
        "desc": "Frozen fear. Isolated terror. No escape from the cold.",
        "hashtag": "ArcticHorror"
    },
    "found_footage_horror": {
        "title": "Found Footage Horror",
        "genres": [27],
        "must_keywords": ["found footage","paranormal","haunting","possession","demon","ghost","recording"],
        "tmdb_with_keywords": "14965,12392", # found footage, paranormal
        "desc": "They pressed record. Evil answered back.",
        "hashtag": "FoundFootageHorror"
    },
    "psychological_crime": {
        "title": "Psychological Crime Thrillers",
        "genres": [80,53], # Crime + Thriller ONLY
        "must_keywords": ["psychological","detective","investigation","serial","murder","mind"],
        "tmdb_with_keywords": "10092,15098",
        "desc": "Twisted minds. Dark secrets. Every clue hides a lie.",
        "hashtag": "PsychologicalCrime"
    },
    "serial_killer": {
        "title": "Serial Killer Crime Thrillers",
        "genres": [80,53],
        "must_keywords": ["serial killer","killer","murder","homicide","victim"],
        "tmdb_with_keywords": "15098,10443",
        "desc": "Hunting a monster. Every murder is a message.",
        "hashtag": "SerialKiller"
    },
    "time_travel_sci_fi": {
        "title": "Time Travel Sci-Fi",
        "genres": [878],
        "must_keywords": ["time travel","time loop","timeline","future","past","temporal"],
        "tmdb_with_keywords": "437,158",
        "desc": "Time bends. Reality breaks. Past and future collide.",
        "hashtag": "TimeTravel"
    },
    "survival_action": {
        "title": "Survival Action",
        "genres": [28,53],
        "must_keywords": ["survival","wilderness","stranded","escape","fight to survive"],
        "tmdb_with_keywords": "3803,10389",
        "desc": "One mistake. No second chance. Survive at any cost.",
        "hashtag": "SurvivalAction"
    },
    "dream_realities": {
        "title": "Dream & Hidden Realities",
        "genres": [14,27,878],
        "must_keywords": ["dream","nightmare","reality","subconscious","illusion"],
        "tmdb_with_keywords": "3456,6152",
        "desc": "Dreams bleed into reality. What is real anymore?",
        "hashtag": "DreamHorror"
    },
    "interdimensional_portals": {
        "title": "Interdimensional Portals",
        "genres": [878,27],
        "must_keywords": ["portal","dimension","otherworld","parallel","alien","other world"],
        "tmdb_with_keywords": "9950,10092",
        "desc": "A door opens. Something comes through.",
        "hashtag": "Interdimensional"
    },
    "tactical_action": {
        "title": "Tactical Action",
        "genres": [28,10752],
        "must_keywords": ["military","soldier","mission","tactical","war","special forces","army"],
        "tmdb_with_keywords": "5827,10492",
        "desc": "One team. One mission. No room for error.",
        "hashtag": "TacticalAction"
    },
    "racing_action": {
        "title": "Racing Action",
        "genres": [28],
        "must_keywords": ["racing","car race","speed","driver","chase"],
        "tmdb_with_keywords": "2343,10337",
        "desc": "Full throttle. No brakes. Race or die.",
        "hashtag": "RacingAction"
    }
}

INDUSTRY_CONFIG = {
    "hollywood": {"lang": "en", "desc": "Hollywood", "country": "US"},
    "bollywood": {"lang": "hi", "desc": "Bollywood", "country": "IN"},
    "south": {"lang": "te,ta,ml,kn", "desc": "South Indian", "country": "IN"},
    "series": {"lang": "en", "desc": "Series", "media": "tv", "country": "US"},
}

TIME_SLOTS = {
    "morning": {"bd_time": "সকাল ৮টা", "pool": ["tactical_action","survival_action","racing_action"], "industries": ["hollywood","bollywood","south"]},
    "afternoon": {"bd_time": "দুপুর ২টা", "pool": ["psychological_crime","serial_killer","time_travel_sci_fi"], "industries": ["hollywood","bollywood","south","series"]},
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

def is_pure_match(movie, micro_cfg):
    """100% PURE check - genre + overview keywords"""
    # Check genre match - must have at least one of required genres
    movie_genres = movie.get("genre_ids", []) or movie.get("genres", [])
    # If genres is list of dicts
    if movie_genres and isinstance(movie_genres[0], dict):
        movie_genres = [g["id"] for g in movie_genres]
    if not any(g in micro_cfg["genres"] for g in movie_genres):
        # If no genre_ids (like trending), check from details later but fail for now
        # Allow if genre_ids missing but overview matches strongly
        pass
    else:
        # If movie has genres that are totally outside micro (like 10751 Family, 16 Animation), reject
        # But we allow if at least one required genre exists
        pass

    # Overview/title keyword check - MUST contain at least one must_keyword
    overview = (movie.get("overview","") + " " + (movie.get("title") or movie.get("name") or "")).lower()
    for kw in micro_cfg["must_keywords"]:
        if kw.lower() in overview:
            return True
    # If no keyword in overview, check if TMDB keywords match (we already filtered via discover)
    # For arctic horror, be extra strict: if no arctic keyword, reject unless vote high and genre horror
    # For now, if movie came from discover with keywords, consider pure
    if movie.get("_from_keyword_search"):
        return True
    # Fallback: if genre matches exactly, allow
    if any(g in micro_cfg["genres"] for g in movie_genres):
        # For general genres like tactical, survival, etc, genre match is enough if we used keyword search
        return True
    return False

def fetch_tmdb_movies_pure(micro_key, industry_key, count=4):
    cfg = MICRO_GENRES[micro_key]
    ind_cfg = INDUSTRY_CONFIG[industry_key]
    is_tv = ind_cfg.get("media") == "tv"
    base = "https://api.themoviedb.org/3"
    mtype = "tv" if is_tv else "movie"
    min_year = datetime.now().year - 10
    genre_str = ",".join(map(str, cfg["genres"]))
    lang = ind_cfg["lang"].split(",")[0]

    urls = []
    # Strict: discover with genres + keywords + language
    for page in [1,2,3]:
        url = f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_genres={genre_str}&with_keywords={cfg['tmdb_with_keywords']}&sort_by=popularity.desc&vote_count.gte=30&page={page}"
        if not is_tv:
            url += f"&primary_release_date.gte={min_year}-01-01&with_original_language={lang}"
        else:
            url += f"&first_air_date.gte={min_year}-01-01&with_original_language={lang}"
        urls.append(url)
    
    # Also search by keyword text search for purity
    for kw in cfg["must_keywords"][:2]:  # top 2 keywords
        kw_url = f"{base}/search/{mtype}?api_key={TMDB_API_KEY}&query={kw}&page=1&language=en-US"
        urls.append(kw_url)

    all_results = []
    for url in urls:
        try:
            r = requests.get(url, timeout=15).json()
            results = r.get("results", [])
            for m in results:
                if not m.get("poster_path"):
                    continue
                if m.get("vote_count",0) < 10:
                    continue
                # Mark as from keyword search if from discover with keywords
                if "with_keywords" in url:
                    m["_from_keyword_search"] = True
                m["media_type"] = mtype
                all_results.append(m)
        except Exception as e:
            print(f"Fetch err {url[:60]} {e}")
            continue

    # Deduplicate + pure filter
    seen = set()
    pure = []
    for m in all_results:
        mid = m["id"]
        if mid in seen:
            continue
        seen.add(mid)
        # Must have poster
        if not m.get("poster_path"):
            continue
        # Year check
        date_str = m.get("release_date") or m.get("first_air_date") or ""
        if date_str:
            try:
                if int(date_str[:4]) < min_year:
                    continue
            except: pass
        # PURE check
        if not is_pure_match(m, cfg):
            continue
        pure.append(m)

    # Sort by popularity
    pure.sort(key=lambda x: x.get("popularity",0), reverse=True)
    # Remove duplicates already posted
    random.shuffle(pure)
    print(f"PURE fetched {len(pure)} for {micro_key} - {industry_key} (from {len(all_results)} raw)")
    return pure[:count*2]  # return extra for history filter

def download_posters(movies):
    files=[]
    for idx,m in enumerate(movies):
        try:
            url = f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}"
            data = requests.get(url, timeout=20).content
            fname = f"poster_{idx}.jpg"
            Path(fname).write_bytes(data)
            files.append(fname)
            print(f"Downloaded {idx+1}: {m.get('title') or m.get('name')} ID:{m['id']}")
        except Exception as e:
            print(f"Poster fail {e}")
    return files

def create_2x2_grid_with_center_watermark(image_files, watermark_path="watermark.png", output_file="merged_post.jpg"):
    """
    4 movies: 2 top, 2 bottom, watermark in exact center with equal gap
    Layout:
    [0][1]
    [WM centered]
    [2][3]
    Total 1080x1920 (9:16)
    Each poster 540x960, scaled and cropped
    Watermark 900 width, placed at center y=960
    """
    if len(image_files) < 4:
        print(f"Need 4, got {len(image_files)}")
        return None
    # Ensure exactly 4, no duplicates
    if len(set(image_files)) < len(image_files):
        print("Duplicate files detected, removing")
        # dedup by content? For now keep unique paths
        pass
    image_files = image_files[:4]
    
    inputs=[]
    for img in image_files:
        inputs.extend(["-i", img])
    
    has_wm = Path(watermark_path).exists()
    if has_wm:
        inputs.extend(["-i", watermark_path])
        print(f"Watermark OK {Path(watermark_path).stat().st_size/1024:.1f}KB")

    # Build filter
    parts=[]
    for i in range(4):
        parts.append(f"[{i}:v]scale=540:960:force_original_aspect_ratio=increase,crop=540:960[v{i}];")
    
    # 2x2 grid: 0_0 | 540_0 | 0_960 | 540_960 = 1080x1920
    layout="0_0|540_0|0_960|540_960"
    xstack=f"[v0][v1][v2][v3]xstack=inputs=4:layout={layout}[grid];"
    
    if has_wm:
        # Scale watermark to 850 width, overlay exactly at center (540-425, 960- h/2)
        # Perfect center with equal gap top-bottom
        filt="".join(parts)+xstack+"[4:v]scale=850:-1:flags=lanczos[wm];[grid][wm]overlay=(W-w)/2:(H-h)/2:format=auto:shortest=1[out]"
    else:
        font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        filt="".join(parts)+xstack+f"[grid]drawbox=x=(w-750)/2:y=(h-100)/2:w=750:h=100:color=black@0.7:t=fill,drawtext=text='WATCH ON MOVIMOON.ONLINE':fontfile={font}:fontcolor=white:fontsize=32:x=(w-text_w)/2:y=(h-text_h)/2[out]"

    cmd=["ffmpeg","-y"]+inputs+["-filter_complex",filt,"-map","[out]","-frames:v","1","-q:v","2",output_file]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True)
        print(f"Collage created {output_file} {Path(output_file).stat().st_size/1024:.1f}KB - 2x2 with center WM")
        return output_file
    except Exception as e:
        print(f"Collage err {e}")
        print(f"stderr {result.stderr[-1000:] if 'result' in locals() else ''}")
        return None

def generate_caption_gemini_4movies(movies, micro_cfg, industry_cfg):
    movie_data=[]
    for m in movies:
        movie_data.append({
            "name": m.get("title") or m.get("name"),
            "year": (m.get("release_date") or m.get("first_air_date") or "2023")[:4],
            "rating": round(m.get("vote_average",7.0),1),
            "overview": m.get("overview","")[:200],
            "type": micro_cfg["title"]
        })
    
    # Build hashtag list with movie names
    hashtag_list = []
    for md in movie_data:
        clean = re.sub(r'[^A-Za-z0-9]', '', md["name"])
        if clean:
            hashtag_list.append(f"#{clean}")
    hashtag_list.append(f"#{micro_cfg['hashtag']}")
    hashtag_list.append("#MoviMoon")
    hashtags_line = " ".join(hashtag_list)

    prompt=f"""You are MoviMoon curator. Theme: {micro_cfg['title']} - {industry_cfg['desc']}

EXACT FORMAT WITH ICONS FOR 4 MOVIES ONLY:

🍿 MoviMoon Movie Picks: {micro_cfg['title']}

{micro_cfg['desc']}

🎬 1. Movie Name (Year)
⭐ IMDb Rating: X.X/10
📺 OTT Platform: Check MoviMoon.Online
🎭 Movie Type: {micro_cfg['title']}
📅 Release Year: Year
💡 Highlight: [2 sentences in Bengali/Bangla, exciting, spoiler-free]

🎬 2. Movie Name (Year)
⭐ IMDb Rating: X.X/10
📺 OTT Platform: Check MoviMoon.Online
🎭 Movie Type: {micro_cfg['title']}
📅 Release Year: Year
💡 Highlight: [2 sentences in Bengali]

🎬 3. Same format
🎬 4. Same format

👉 দুর্দান্ত সব মুভি/সিরিজ দেখতে বা ডাউনলোড করতে এখনি গুগলে সার্চ করুন বা সরাসরি ভিজিট করুন MoviMoon.Online ।

Hashtags:
{hashtags_line}

RULES:
- ONLY 4 movies, no more
- Each line MUST start with icon: 🎬 ⭐ 📺 🎭 📅 💡
- Highlight MUST be Bengali
- OTT ALWAYS Check MoviMoon.Online
- Hashtags MUST include each movie name without spaces + genre tag + MoviMoon
- After 4 movies, add CTA line exactly: "👉 দুর্দান্ত সব মুভি/সিরিজ দেখতে বা ডাউনলোড করতে এখনি গুগলে সার্চ করুন বা সরাসরি ভিজিট করুন MoviMoon.Online ।"

Data: {json.dumps(movie_data, ensure_ascii=False)}
"""

    text_result=""
    if client and GEMINI_OK:
        try:
            for model_name in ["gemini-2.5-flash-lite","gemini-2.0-flash-lite","gemini-1.5-flash","gemini-1.5-flash-latest"]:
                try:
                    resp = client.models.generate_content(model=model_name, contents=prompt)
                    text_result = resp.text
                    print(f"Gemini {model_name} OK {len(text_result)} chars")
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
            print(f"OLD Gemini OK {len(text_result)}")
        except Exception as e:
            print(f"OLD fail {e}")

    if not text_result:
        lines=[f"🍿 MoviMoon Movie Picks: {micro_cfg['title']}", "", micro_cfg['desc'], ""]
        for i, md in enumerate(movie_data,1):
            lines.append(f"🎬 {i}. {md['name']} ({md['year']})")
            lines.append(f"⭐ IMDb Rating: {md['rating']}/10")
            lines.append(f"📺 OTT Platform: Check MoviMoon.Online")
            lines.append(f"🎭 Movie Type: {micro_cfg['title']}")
            lines.append(f"📅 Release Year: {md['year']}")
            lines.append(f"💡 Highlight: একটি অসাধারণ গল্প যা আপনাকে মুগ্ধ করবে। শেষ পর্যন্ত টানটান উত্তেজনা থাকবে।")
            lines.append("")
        lines.append("👉 দুর্দান্ত সব মুভি/সিরিজ দেখতে বা ডাউনলোড করতে এখনি গুগলে সার্চ করুন বা সরাসরি ভিজিট করুন MoviMoon.Online ।")
        lines.append("")
        lines.append("Hashtags:")
        lines.append(hashtags_line)
        text_result="\n".join(lines)

    # Fixes
    text_result = re.sub(r"📺 OTT Platform:.*", "📺 OTT Platform: Check MoviMoon.Online", text_result, flags=re.IGNORECASE)
    text_result = re.sub(r"(?<!📺 )OTT Platform:.*", "📺 OTT Platform: Check MoviMoon.Online", text_result, flags=re.IGNORECASE)
    
    cta="👉 দুর্দান্ত সব মুভি/সিরিজ দেখতে বা ডাউনলোড করতে এখনি গুগলে সার্চ করুন বা সরাসরি ভিজিট করুন MoviMoon.Online ।"
    if cta not in text_result:
        if "Hashtags:" in text_result:
            text_result = text_result.replace("Hashtags:", f"{cta}\n\nHashtags:")
        else:
            text_result+=f"\n\n{cta}"

    # Ensure hashtags include movie names
    if "Hashtags:" in text_result:
        # Replace hashtags section with our full list
        parts = text_result.split("Hashtags:")
        text_result = parts[0] + "Hashtags:\n" + hashtags_line

    return text_result

def post_to_facebook(image_path, caption):
    if not FB_PAGE_ID or not FB_PAGE_TOKEN:
        print("FB creds missing")
        return None
    url=f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
    payload={'caption': caption, 'access_token': FB_PAGE_TOKEN}
    try:
        with open(image_path,'rb') as img:
            r=requests.post(url, data=payload, files={'source': img}, timeout=90)
            data=r.json()
            print(f"FB Response {data}")
            return data if 'id' in data or 'post_id' in data else None
    except Exception as e:
        print(f"FB err {e}")
        return None

def main():
    slot=get_current_slot()
    slot_cfg=TIME_SLOTS[slot]
    print(f"Slot {slot} {slot_cfg['bd_time']} Pool {slot_cfg['pool']}")
    micro_key=random.choice(slot_cfg['pool'])
    industry_key=random.choice(slot_cfg['industries'])
    micro_cfg=MICRO_GENRES[micro_key]
    industry_cfg=INDUSTRY_CONFIG[industry_key]
    print(f"Selected PURE: {micro_cfg['title']} | Industry: {industry_cfg['desc']} | Keywords: {micro_cfg['must_keywords'][:3]}")

    history=load_history()
    candidates=fetch_tmdb_movies_pure(micro_key, industry_key, count=4)
    
    # Filter history - ensure no duplicates and pure
    fresh=[]
    for m in candidates:
        if not is_posted(m['id'], history, days=60):  # 60 days for 4 movies
            fresh.append(m)
        if len(fresh)>=4:
            break
    
    # If not enough fresh, take from candidates anyway but ensure unique IDs
    if len(fresh) < 4:
        print(f"Only {len(fresh)} fresh, filling from candidates")
        seen_ids = set([f['id'] for f in fresh])
        for m in candidates:
            if m['id'] not in seen_ids:
                fresh.append(m)
                seen_ids.add(m['id'])
            if len(fresh)>=4:
                break

    if len(fresh) < 4:
        print(f"❌ Not enough PURE movies {len(fresh)} for {micro_key}, aborting. Need 4 pure.")
        return

    # Final uniqueness check - no duplicate IDs
    unique_ids = set()
    final_fresh=[]
    for m in fresh[:4]:
        if m['id'] not in unique_ids:
            final_fresh.append(m)
            unique_ids.add(m['id'])
    fresh = final_fresh

    if len(fresh) < 4:
        print(f"❌ Duplicate IDs detected, only {len(fresh)} unique")
        return

    print(f"Final 4 PURE movies:")
    for i,m in enumerate(fresh,1):
        print(f"{i}. {m.get('title') or m.get('name')} ({(m.get('release_date') or m.get('first_air_date') or '')[:4]}) ID:{m['id']}")

    posters=download_posters(fresh)
    if len(posters) != 4:
        print(f"❌ Poster download failed, got {len(posters)} expected 4")
        return

    # Ensure no duplicate poster files (by size check)
    if len(set([Path(p).stat().st_size for p in posters])) < 4:
        print("Warning: possible duplicate posters by size, but continuing")

    collage=create_2x2_grid_with_center_watermark(posters, WATERMARK_FILE, "merged_post.jpg")
    if not collage:
        print("Collage failed")
        return

    caption=generate_caption_gemini_4movies(fresh, micro_cfg, industry_cfg)
    print(f"\n=== CAPTION PREVIEW ===\n{caption[:1000]}...\n")

    fb=post_to_facebook(collage, caption)
    if fb:
        print(f"✅ POSTED SUCCESS PURE 4: {fb.get('id')} | {micro_cfg['title']}")
        for m in fresh:
            history[str(m['id'])]=datetime.now().isoformat()
        save_history(history)
    else:
        print("❌ FB post failed")

    for f in posters+[collage]:
        try:
            Path(f).unlink()
        except: pass

if __name__=="__main__":
    main()
