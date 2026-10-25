import os, requests, random, re, time, json, subprocess
from datetime import datetime, timedelta
from pathlib import Path

print("=== MoviMoon Movie Picks AutoPoster V1 - Micro-Genre Pure 9:16 Collage ===")

# ENV
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN") or os.getenv("FB_ACCESS_TOKEN")

HISTORY_FILE = "picks_history.json"

try:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-3.5-flash-lite")
    GEMINI_OK = True
    print("Gemini OK")
except Exception as e:
    GEMINI_OK = False
    print(f"Gemini fail {e}")

# ========== MICRO-GENRE DATABASE - PURE, NO MIX ==========
MICRO_GENRES = {
    # Hollywood style - from user's images
    "arctic_horror": {
        "title": "Arctic Horror",
        "title_bn": "বরফের রাজ্যে আতঙ্ক",
        "genres": [27, 53],
        "keywords": ["arctic", "snow", "ice", "frozen", "blizzard", "cold", "winter", "glacier"],
        "tmdb_keywords": "1930,207317",  # snow, arctic approximation
        "desc": "Frozen fear. Isolated terror. No escape from the cold.",
        "industry": "hollywood"
    },
    "psychological_crime": {
        "title": "Psychological Crime Thrillers",
        "title_bn": "মনস্তাত্ত্বিক ক্রাইম থ্রিলার",
        "genres": [80, 53, 9648],
        "keywords": ["psychological", "mind", "detective", "serial", "killer", "investigation"],
        "tmdb_keywords": "10092,15098",
        "desc": "Twisted minds. Dark secrets. Every clue hides a lie.",
        "industry": "hollywood"
    },
    "time_travel_sci_fi": {
        "title": "Time Travel Sci-Fi",
        "title_bn": "টাইম ট্রাভেল সায়েন্স ফিকশন",
        "genres": [878, 53, 9648],
        "keywords": ["time travel", "time loop", "future", "past", "timeline"],
        "tmdb_keywords": "437,158,207170",
        "desc": "Time bends. Reality breaks. Past and future collide.",
        "industry": "hollywood"
    },
    "survival_action": {
        "title": "Survival Action",
        "title_bn": "বেঁচে থাকার লড়াই",
        "genres": [28, 12, 53],
        "keywords": ["survival", "fight", "escape", "wilderness", "battle"],
        "tmdb_keywords": "3803,1645",
        "desc": "One mistake. No second chance. Survive at any cost.",
        "industry": "hollywood"
    },
    "dream_realities": {
        "title": "Dream Connections & Hidden Realities",
        "title_bn": "স্বপ্ন ও লুকানো বাস্তবতা",
        "genres": [14, 27, 878],
        "keywords": ["dream", "reality", "hidden", "nightmare", "subconscious"],
        "tmdb_keywords": "3456",
        "desc": "Dreams bleed into reality. What is real anymore?",
        "industry": "hollywood"
    },
    "serial_killer": {
        "title": "Serial Killer Crime Thrillers",
        "title_bn": "সিরিয়াল কিলার ক্রাইম",
        "genres": [80, 53, 27],
        "keywords": ["serial killer", "murder", "detective", "killer", "victim"],
        "tmdb_keywords": "15098",
        "desc": "Hunting a monster. Every murder is a message.",
        "industry": "hollywood"
    },
    "found_footage_horror": {
        "title": "Found Footage Horror",
        "title_bn": "ফাউন্ড ফুটেজ হরর",
        "genres": [27, 9648],
        "keywords": ["found footage", "rec", "paranormal", "haunting", "camera"],
        "tmdb_keywords": "14965",
        "desc": "They pressed record. Evil answered back.",
        "industry": "hollywood"
    },
    "interdimensional_portals": {
        "title": "Interdimensional Portals & Otherworldly Threats",
        "title_bn": "অন্য জগতের দরজা",
        "genres": [878, 27, 14],
        "keywords": ["portal", "dimension", "otherworld", "alien", "parallel"],
        "tmdb_keywords": "10092,9950",
        "desc": "A door opens. Something comes through.",
        "industry": "hollywood"
    },
    "tactical_action": {
        "title": "Tactical Action",
        "title_bn": "ট্যাকটিক্যাল অ্যাকশন",
        "genres": [28, 10752, 80],
        "keywords": ["tactical", "military", "soldier", "mission", "war", "special forces"],
        "tmdb_keywords": "5827,10492",
        "desc": "One team. One mission. No room for error.",
        "industry": "hollywood"
    },
    "racing_action": {
        "title": "Racing & High-Octane Action",
        "title_bn": "রেসিং ও হাই-অকটেন অ্যাকশন",
        "genres": [28, 12],
        "keywords": ["racing", "car", "speed", "chase", "drive"],
        "tmdb_keywords": "2343,10337",
        "desc": "Full throttle. No brakes. Race or die.",
        "industry": "hollywood"
    }
}

# Bollywood & South & Series variants - same micro-genre but different industry
INDUSTRY_CONFIG = {
    "hollywood": {"lang": "en", "country": "US", "desc": "Hollywood"},
    "bollywood": {"lang": "hi", "country": "IN", "desc": "Bollywood"},
    "south": {"lang": "te,ta,ml,kn", "country": "IN", "desc": "South Indian"},
    "series": {"lang": "en", "country": "US", "desc": "Series", "media": "tv"},
    "k_series": {"lang": "ko", "country": "KR", "desc": "K-Drama Series", "media": "tv"}
}

# Time slot to micro-genre pool
TIME_SLOTS = {
    "morning": {  # 8AM BD - High Energy
        "bd_time": "সকাল ৮টা",
        "pool": ["tactical_action", "survival_action", "racing_action"],
        "industries": ["hollywood", "bollywood", "south"]
    },
    "afternoon": {  # 2PM BD - Brain Teaser
        "bd_time": "দুপুর ২টা",
        "pool": ["psychological_crime", "time_travel_sci_fi", "serial_killer"],
        "industries": ["hollywood", "bollywood", "south", "series"]
    },
    "night": {  # 9PM BD - Dark Horror
        "bd_time": "রাত ৯টা",
        "pool": ["arctic_horror", "found_footage_horror", "interdimensional_portals", "dream_realities"],
        "industries": ["hollywood", "bollywood", "series"]
    }
}

def get_current_slot():
    hour_utc = datetime.utcnow().hour
    # 2 UTC = 8AM BD, 8 UTC = 2PM BD, 15 UTC = 9PM BD
    if 1 <= hour_utc <= 4:
        return "morning"
    elif 7 <= hour_utc <= 10:
        return "afternoon"
    else:
        return "night"

def load_history():
    try:
        if Path(HISTORY_FILE).exists():
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_history(h):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(h, f, indent=2)
    except Exception as e:
        print(f"History save err {e}")

def is_posted(tmdb_id, history, days=30):
    tmdb_id = str(tmdb_id)
    if tmdb_id not in history:
        return False
    try:
        last = datetime.fromisoformat(history[tmdb_id])
        if datetime.now() - last < timedelta(days=days):
            return True
    except:
        return False
    return False

def fetch_tmdb_movies_micro(micro_key, industry_key, count=9):
    cfg = MICRO_GENRES[micro_key]
    ind_cfg = INDUSTRY_CONFIG[industry_key]
    genre_ids = cfg["genres"]
    is_tv = ind_cfg.get("media") == "tv"
    
    # Build discover URL
    base = "https://api.themoviedb.org/3"
    mtype = "tv" if is_tv else "movie"
    
    # Date filter - last 15 years for hype
    min_year = datetime.now().year - 15
    
    params_list = []
    
    # Popular + Trending + Discover mix
    urls = []
    
    # Discover with genre
    genre_str = ",".join(map(str, genre_ids))
    
    if is_tv:
        # Series
        urls.append(f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_genres={genre_str}&first_air_date.gte={min_year}-01-01&sort_by=popularity.desc&vote_count.gte=50&page=1&with_original_language={ind_cfg['lang'].split(',')[0]}")
        urls.append(f"{base}/trending/{mtype}/week?api_key={TMDB_API_KEY}&language=en-US")
    else:
        # Movies
        lang_param = ind_cfg['lang'].split(',')[0]
        if industry_key == "hollywood":
            urls.append(f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_genres={genre_str}&primary_release_date.gte={min_year}-01-01&sort_by=popularity.desc&vote_count.gte=100&with_original_language=en&page=1")
            urls.append(f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_genres={genre_str}&sort_by=vote_average.desc&vote_count.gte=300&page=1")
        elif industry_key == "bollywood":
            urls.append(f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_genres={genre_str}&primary_release_date.gte={min_year}-01-01&sort_by=popularity.desc&vote_count.gte=20&with_original_language=hi&page=1")
            urls.append(f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_original_language=hi&sort_by=popularity.desc&page=1")
        elif industry_key == "south":
            for l in ["te","ta","ml","kn"]:
                urls.append(f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_genres={genre_str}&primary_release_date.gte={min_year}-01-01&sort_by=popularity.desc&with_original_language={l}&page=1")
    
    # Also trending for hype
    urls.append(f"{base}/trending/{mtype}/week?api_key={TMDB_API_KEY}")
    
    all_results = []
    for url in urls:
        try:
            r = requests.get(url, timeout=15).json()
            results = r.get("results", [])
            for m in results:
                m['media_type'] = mtype
                # Ensure poster
                if not m.get("poster_path"):
                    continue
                # Filter year
                date_str = m.get("release_date") or m.get("first_air_date") or ""
                if date_str:
                    try:
                        y = int(date_str[:4])
                        if y < min_year:
                            continue
                    except:
                        pass
                all_results.append(m)
        except Exception as e:
            print(f"TMDB fetch err {e} for {url[:80]}")
            continue
    
    # Deduplicate and filter by hype
    seen = set()
    unique = []
    for m in all_results:
        mid = m['id']
        if mid not in seen:
            # Hype filter
            pop = m.get("popularity", 0)
            vote = m.get("vote_average", 0)
            if pop < 10 and vote < 5:
                continue
            unique.append(m)
            seen.add(mid)
    
    # Sort by popularity + vote
    unique.sort(key=lambda x: (x.get("popularity",0)*0.7 + x.get("vote_average",0)*10), reverse=True)
    
    random.shuffle(unique)
    # Return 9
    print(f"Fetched {len(unique)} for {micro_key} - {industry_key}")
    return unique[:count]

def download_posters(movies):
    files = []
    for idx, m in enumerate(movies):
        try:
            poster_path = m.get("poster_path")
            if not poster_path:
                continue
            url = f"https://image.tmdb.org/t/p/w500{poster_path}"
            data = requests.get(url, timeout=20).content
            fname = f"poster_{idx}.jpg"
            with open(fname, "wb") as f:
                f.write(data)
            files.append(fname)
            print(f"Downloaded poster {idx+1}: {m.get('title') or m.get('name')}")
        except Exception as e:
            print(f"Poster download fail {e}")
    return files

def create_916_grid_with_watermark(image_files, output_file="merged_post.jpg"):
    count = len(image_files)
    if count == 0:
        print("No images to merge")
        return None
    
    # Ensure 9, if less than 9 duplicate or use what we have but we need 9 for perfect grid
    # If less than 9, we will create grid with available but layout adjusted
    # For simplicity, require at least 6
    if count < 6:
        print(f"Only {count} posters, need at least 6")
        return None
    
    # If 7 or 8, pad to 9 by duplicating last
    while len(image_files) < 9 and count >=6:
        image_files.append(image_files[-1])
        count = len(image_files)
    
    inputs = []
    for img in image_files[:9]:
        inputs.extend(["-i", img])
    
    # 3x3 grid 1080x1920
    # Each cell 360x640
    filter_parts = []
    for i in range(9):
        filter_parts.append(f"[{i}:v]scale=360:640:force_original_aspect_ratio=increase,crop=360:640[v{i}];")
    
    xstack_layout = "0_0|360_0|720_0|0_640|360_640|720_640|0_1280|360_1280|720_1280"
    xstack = f"[v0][v1][v2][v3][v4][v5][v6][v7][v8]xstack=inputs=9:layout={xstack_layout}[grid];"
    
    # Watermark: black box + white text centered
    # Use DejaVuSans-Bold
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    # Check font exists, else try other
    if not Path(font_path).exists():
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    
    # Draw semi-transparent black box in center + text
    # Box 750x100 at center
    watermark_filter = (
        f"[grid]drawbox=x=(w-750)/2:y=(h-110)/2:w=750:h=110:color=black@0.65:t=fill,"
        f"drawtext=text='watch on movimoon.online':fontfile={font_path}:fontcolor=white:fontsize=36:"
        f"x=(w-text_w)/2:y=(h-text_h)/2:box=0[out]"
    )
    
    full_filter = "".join(filter_parts) + xstack + watermark_filter
    
    cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", full_filter, "-map", "[out]", "-frames:v", "1", "-q:v", "2", output_file]
    
    print(f"FFmpeg collage cmd: {' '.join(cmd[:10])}... filter len {len(full_filter)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if Path(output_file).exists():
            print(f"Collage created: {output_file} {Path(output_file).stat().st_size/1024:.1f}KB")
            return output_file
        else:
            print(f"FFmpeg failed: {result.stderr[-1000:]}")
            # Fallback without watermark font
            fallback_filter = "".join(filter_parts) + f"[v0][v1][v2][v3][v4][v5][v6][v7][v8]xstack=inputs=9:layout={xstack_layout}[out]"
            cmd2 = ["ffmpeg", "-y"] + inputs + ["-filter_complex", fallback_filter, "-map", "[out]", "-frames:v", "1", output_file]
            subprocess.run(cmd2, check=True, timeout=60)
            # Second pass watermark with simpler drawbox
            cmd3 = ["ffmpeg", "-y", "-i", output_file, "-vf", "drawbox=x=(w-700)/2:y=(h-100)/2:w=700:h=100:color=black@0.6:t=fill", "-q:v", "2", "temp_"+output_file]
            subprocess.run(cmd3, check=True, timeout=30)
            Path("temp_"+output_file).rename(output_file)
            return output_file
    except Exception as e:
        print(f"Collage error {e}")
        import traceback; traceback.print_exc()
        return None

def generate_caption_gemini(movies, micro_cfg, industry_cfg):
    if not GEMINI_OK:
        # Fallback
        title = f"🍿 MoviMoon Movie Picks: {micro_cfg['title']}"
        lines = [title, "", micro_cfg['desc'], ""]
        for i, m in enumerate(movies, 1):
            name = m.get("title") or m.get("name")
            year = (m.get("release_date") or m.get("first_air_date") or "")[:4]
            rating = m.get("vote_average", 7.0)
            lines.append(f"{i}. {name} ({year})")
            lines.append(f"- IMDb Rating: {rating:.1f}/10")
            lines.append(f"- OTT Platform: Check MoviMoon.Online")
            lines.append(f"- Movie Type: {micro_cfg['title']}")
            lines.append(f"- Release Year: {year}")
            lines.append(f"- Highlight: একটি অসাধারণ গল্প যা আপনাকে মুগ্ধ করবে।")
        return "\n".join(lines)
    
    movie_data = []
    for m in movies:
        movie_data.append({
            "name": m.get("title") or m.get("name"),
            "year": (m.get("release_date") or m.get("first_air_date") or "2023")[:4],
            "rating": round(m.get("vote_average", 7.0), 1),
            "overview": m.get("overview", "")[:200],
            "type": micro_cfg['title']
        })
    
    prompt = f"""You are professional movie curator for MoviMoon Facebook Page.

Create Facebook post for 9 movies with EXACT format. Theme: {micro_cfg['title']} - {industry_cfg['desc']}

CRITICAL FORMAT - Follow exactly:

🍿 MoviMoon Movie Picks: {micro_cfg['title']}

{micro_cfg['desc']}

1. Movie Name (Year)
- IMDb Rating: X.X/10
- OTT Platform: Check MoviMoon.Online
- Movie Type: {micro_cfg['title']}
- Release Year: Year
- Highlight: [2 sentences in BENGALI, compelling, spoiler-free, must be Bengali]

2. Movie Name (Year)
... same format for all 9

Hashtags:
#MovieNameWithoutSpace #GenreTag #MoviMoon

Rules:
- OTT Platform ALWAYS: Check MoviMoon.Online (never Netflix etc)
- Highlight MUST be Bengali (Bangla language)
- Highlight 2 sentences, exciting, no spoiler
- Movie names from data, years accurate
- Keep IMDb rating from data
- End with hashtags

Movie Data:
{json.dumps(movie_data, ensure_ascii=False, indent=2)}
"""
    try:
        response = gemini_model.generate_content(prompt)
        text = response.text
        # Ensure OTT Platform fix
        text = re.sub(r"OTT Platform:.*", "OTT Platform: Check MoviMoon.Online", text, flags=re.IGNORECASE)
        print(f"Gemini caption generated {len(text)} chars")
        return text
    except Exception as e:
        print(f"Gemini err {e}")
        import traceback; traceback.print_exc()
        return generate_caption_gemini(movies, micro_cfg, industry_cfg) if not GEMINI_OK else f"🍿 MoviMoon Movie Picks: {micro_cfg['title']}\n\n{json.dumps(movie_data, ensure_ascii=False)}"

def post_to_facebook(image_path, caption):
    if not FB_PAGE_ID or not FB_PAGE_TOKEN:
        print("FB credentials missing")
        return None
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
    payload = {
        'caption': caption,
        'access_token': FB_PAGE_TOKEN
    }
    try:
        with open(image_path, 'rb') as img:
            files = {'source': img}
            r = requests.post(url, data=payload, files=files, timeout=60)
            data = r.json()
            print(f"FB Response: {data}")
            if 'id' in data or 'post_id' in data:
                return data
            else:
                print(f"FB post failed: {data}")
                return None
    except Exception as e:
        print(f"FB post error {e}")
        return None

def main():
    print(f"=== Starting Movie Picks AutoPoster at {datetime.now()} ===")
    slot = get_current_slot()
    slot_cfg = TIME_SLOTS[slot]
    print(f"Slot: {slot} - {slot_cfg['bd_time']} | Pool: {slot_cfg['pool']}")
    
    # Pick micro-genre
    micro_key = random.choice(slot_cfg['pool'])
    industry_key = random.choice(slot_cfg['industries'])
    
    micro_cfg = MICRO_GENRES[micro_key]
    industry_cfg = INDUSTRY_CONFIG[industry_key]
    
    print(f"Selected: {micro_cfg['title']} | Industry: {industry_cfg['desc']} ({industry_key})")
    
    history = load_history()
    
    # Fetch movies
    movies = fetch_tmdb_movies_micro(micro_key, industry_key, count=9)
    
    # Filter out already posted
    fresh = [m for m in movies if not is_posted(m['id'], history, days=30)]
    if len(fresh) < 6:
        # If too many repeats, take all
        fresh = movies
        print(f"Too many repeats, using all {len(movies)}")
    
    # Limit 9
    fresh = fresh[:9]
    
    if len(fresh) < 6:
        print(f"Not enough movies {len(fresh)}, abort")
        return
    
    # Download posters
    poster_files = download_posters(fresh)
    if len(poster_files) < 6:
        print(f"Poster download failed, only {len(poster_files)}")
        return
    
    # Create collage
    collage = create_916_grid_with_watermark(poster_files, "merged_post.jpg")
    if not collage:
        print("Collage creation failed")
        return
    
    # Generate caption
    caption = generate_caption_gemini(fresh, micro_cfg, industry_cfg)
    print(f"\n=== CAPTION ===\n{caption[:500]}...\n")
    
    # Post to FB
    fb_res = post_to_facebook(collage, caption)
    if fb_res:
        print(f"✅ POSTED SUCCESS: {fb_res.get('id')}")
        # Save history
        for m in fresh:
            history[str(m['id'])] = datetime.now().isoformat()
        save_history(history)
    else:
        print("❌ FB post failed")
    
    # Cleanup
    for f in poster_files + [collage]:
        try:
            if Path(f).exists():
                Path(f).unlink()
        except:
            pass

if __name__ == "__main__":
    main()
