
import os, requests, random, re, json, subprocess
from datetime import datetime, timedelta
from pathlib import Path

print("=== MoviMoon Movie Picks AutoPoster V5 - ORIGINAL Genres + 180px GAP + Real Highlight ===")

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

# ===== V5 - ORIGINAL TMDB GENRES ONLY =====
GENRES = {
    "action": {"id": 28, "title": "Action", "desc": "High-octane action. Non-stop thrills. Adrenaline overload.", "hashtag": "Action"},
    "adventure": {"id": 12, "title": "Adventure", "desc": "Epic journeys. Unknown worlds. Adventure awaits.", "hashtag": "Adventure"},
    "horror": {"id": 27, "title": "Horror", "desc": "Pure terror. Spine-chilling fear. You can't look away.", "hashtag": "Horror"},
    "thriller": {"id": 53, "title": "Thriller", "desc": "Heart-pounding suspense. Every second counts.", "hashtag": "Thriller"},
    "sci_fi": {"id": 878, "title": "Sci-Fi", "desc": "Future tech. Alien worlds. Reality reimagined.", "hashtag": "SciFi"},
    "crime": {"id": 80, "title": "Crime", "desc": "Dark underworld. Criminal minds. Justice has a price.", "hashtag": "Crime"},
    "fantasy": {"id": 14, "title": "Fantasy", "desc": "Magic realms. Mythical creatures. Fantasy comes alive.", "hashtag": "Fantasy"},
    "comedy": {"id": 35, "title": "Comedy", "desc": "Laugh out loud. Pure fun. Comedy gold.", "hashtag": "Comedy"},
    "drama": {"id": 18, "title": "Drama", "desc": "Emotional depth. Powerful stories. Drama at its best.", "hashtag": "Drama"},
    "romance": {"id": 10749, "title": "Romance", "desc": "Love stories. Heartfelt moments. Romance is in the air.", "hashtag": "Romance"},
    "mystery": {"id": 9648, "title": "Mystery", "desc": "Unsolved puzzles. Hidden secrets. Mystery unfolds.", "hashtag": "Mystery"},
    "war": {"id": 10752, "title": "War", "desc": "Battlefield heroism. War stories. Courage under fire.", "hashtag": "War"},
}

INDUSTRY_CONFIG = {
    "hollywood": {"lang": "en", "desc": "Hollywood", "region": "US", "country_filter": "US"},
    "bollywood": {"lang": "hi", "desc": "Bollywood", "region": "IN", "country_filter": "IN"},
    "south": {"lang": "te", "desc": "South Indian", "region": "IN", "langs": ["te","ta","ml","kn"]},
    "series": {"lang": "en", "desc": "Hollywood Series", "media": "tv"},
}

TIME_SLOTS = {
    "morning": {"bd_time": "সকাল ৮টা", "pool": ["action","adventure","war","comedy"], "industries": ["hollywood","bollywood","south"]},
    "afternoon": {"bd_time": "দুপুর ২টা", "pool": ["crime","mystery","drama","romance"], "industries": ["hollywood","bollywood","south","series"]},
    "night": {"bd_time": "রাত ৯টা", "pool": ["horror","thriller","sci_fi","fantasy"], "industries": ["hollywood","bollywood","series"]}
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

def fetch_tmdb_pure_genre(genre_key, industry_key, count=4):
    """V5 - Pure original genre, strict industry filter, no keyword fallback mixing"""
    genre_cfg = GENRES[genre_key]
    ind_cfg = INDUSTRY_CONFIG[industry_key]
    is_tv = ind_cfg.get("media") == "tv"
    base = "https://api.themoviedb.org/3"
    mtype = "tv" if is_tv else "movie"
    genre_id = genre_cfg["id"]
    min_year = datetime.now().year - 12

    urls = []
    # Strict industry filtering
    if industry_key == "hollywood":
        # Hollywood = English language + US region, popular
        for page in [1,2,3]:
            url = f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_genres={genre_id}&primary_release_date.gte={min_year}-01-01&sort_by=popularity.desc&vote_count.gte=50&with_original_language=en&page={page}"
            if is_tv:
                url = f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_genres={genre_id}&first_air_date.gte={min_year}-01-01&sort_by=popularity.desc&vote_count.gte=30&with_original_language=en&page={page}"
            urls.append(url)
    elif industry_key == "bollywood":
        for page in [1,2,3]:
            url = f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_genres={genre_id}&primary_release_date.gte={min_year}-01-01&sort_by=popularity.desc&vote_count.gte=10&with_original_language=hi&page={page}"
            urls.append(url)
    elif industry_key == "south":
        for lang in ind_cfg.get("langs", ["te","ta","ml","kn"]):
            for page in [1,2]:
                url = f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_genres={genre_id}&primary_release_date.gte={min_year}-01-01&sort_by=popularity.desc&vote_count.gte=5&with_original_language={lang}&page={page}"
                urls.append(url)
    elif industry_key == "series":
        for page in [1,2,3]:
            url = f"{base}/discover/{mtype}?api_key={TMDB_API_KEY}&with_genres={genre_id}&first_air_date.gte={min_year}-01-01&sort_by=popularity.desc&vote_count.gte=30&with_original_language=en&page={page}"
            urls.append(url)

    all_results = []
    for url in urls:
        try:
            r = requests.get(url, timeout=15).json()
            for m in r.get("results", []):
                if not m.get("poster_path"): continue
                if m.get("vote_count",0) < 5: continue
                m["media_type"] = mtype
                m["_industry"] = industry_key
                m["_genre"] = genre_key
                all_results.append(m)
        except Exception as e:
            print(f"Fetch err {e}")
            continue

    # Deduplicate and filter pure genre match
    seen = set()
    pure = []
    for m in all_results:
        mid = m["id"]
        if mid in seen: continue
        seen.add(mid)
        # Ensure genre match (TMDB sometimes returns secondary genres)
        gids = m.get("genre_ids", [])
        if genre_id not in gids:
            # If genre_ids missing (TV sometimes), allow but check popularity
            if m.get("popularity",0) < 20:
                continue
        # Year check
        date_str = m.get("release_date") or m.get("first_air_date") or ""
        if date_str:
            try:
                y = int(date_str[:4])
                if y < min_year or y > datetime.now().year + 2:
                    continue
            except: pass
        pure.append(m)

    pure.sort(key=lambda x: x.get("popularity",0), reverse=True)
    random.shuffle(pure)
    print(f"V5 PURE fetched {len(pure)} for {genre_cfg['title']} - {ind_cfg['desc']} (from {len(all_results)} raw)")
    return pure[:count*3]

def download_posters(movies):
    files=[]
    for idx,m in enumerate(movies):
        try:
            url = f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}"
            data = requests.get(url, timeout=20).content
            fname = f"poster_{idx}.jpg"
            Path(fname).write_bytes(data)
            files.append(fname)
            print(f"Downloaded {idx+1}: {m.get('title') or m.get('name')} ID:{m['id']} Lang:{m.get('original_language')} Industry:{m.get('_industry')} Genre:{m.get('_genre')}")
        except Exception as e:
            print(f"Poster fail {e}")
    return files

def create_2x2_grid_with_center_watermark(image_files, watermark_path="watermark.png", output_file="merged_post.jpg"):
    """
    V5 GAP 180px - Watermark in EMPTY SPACE, not on movies
    Total 1080x1920
    Poster size: 540x870 (1920-180)/2 = 870
    Top: y=0
    GAP: 180px (y=870 to 1050)
    Bottom: y=1050
    Watermark: centered in GAP
    """
    if len(image_files) < 4:
        print(f"Need 4, got {len(image_files)}")
        return None
    image_files = image_files[:4]

    inputs=[]
    for img in image_files:
        inputs.extend(["-i", img])
    
    has_wm = Path(watermark_path).exists()
    if has_wm:
        inputs.extend(["-i", watermark_path])
        print(f"Watermark OK {Path(watermark_path).stat().st_size/1024:.1f}KB 1024x179 -> GAP 180px perfect")

    # Scale posters to 540x870
    parts=[]
    for i in range(4):
        parts.append(f"[{i}:v]scale=540:870:force_original_aspect_ratio=increase,crop=540:870:exact=1[v{i}];")
    
    filter_parts = "".join(parts)
    filter_parts += "color=c=black:s=1080x1920:r=30:d=1[bg];"
    filter_parts += "[bg][v0]overlay=0:0[bg1];"
    filter_parts += "[bg1][v1]overlay=540:0[bg2];"
    filter_parts += "[bg2][v2]overlay=0:1050[bg3];"
    filter_parts += "[bg3][v3]overlay=540:1050[withposters];"

    if has_wm:
        # Watermark 1024x179, scale to 900x157 max to fit 180px gap with some padding
        # Fit exactly 900 width, height auto ~157, place at y=870 + (180-157)/2 = 870+11 = 881
        filter_parts += "[4:v]scale=900:-1:eval=frame[wm];"
        filter_parts += "[withposters][wm]overlay=(W-w)/2:870+(180-h)/2:format=auto[out]"
    else:
        font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        filter_parts += f"[withposters]drawbox=x=0:y=870:w=1080:h=180:color=black:t=fill,drawtext=text='WATCH ON MOVIMOON.ONLINE':fontfile={font}:fontcolor=white:fontsize=42:x=(w-text_w)/2:y=870+(180-text_h)/2[out]"

    cmd=["ffmpeg","-y"]+inputs+["-filter_complex",filter_parts,"-map","[out]","-frames:v","1","-q:v","2",output_file]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True)
        print(f"Collage V5 GAP 180px created {output_file} {Path(output_file).stat().st_size/1024:.1f}KB - 2 top + 180px GAP + 2 bottom")
        return output_file
    except Exception as e:
        print(f"Collage V5 err {e}")
        if 'result' in locals():
            print(result.stderr[-2000:])
        return None

def generate_caption_gemini_4movies(movies, genre_cfg, industry_cfg):
    movie_data=[]
    for m in movies:
        movie_data.append({
            "name": m.get("title") or m.get("name"),
            "year": (m.get("release_date") or m.get("first_air_date") or "2023")[:4],
            "rating": round(m.get("vote_average",7.0),1),
            "overview": m.get("overview","")[:400],
            "type": genre_cfg["title"],
            "lang": m.get("original_language"),
            "industry": m.get("_industry")
        })
    
    hashtag_list = []
    for md in movie_data:
        clean = re.sub(r'[^A-Za-z0-9]', '', md["name"])
        if clean:
            hashtag_list.append(f"#{clean}")
    hashtag_list.append(f"#{genre_cfg['hashtag']}")
    hashtag_list.append(f"#{industry_cfg['desc'].replace(' ','')}")
    hashtag_list.append("#MoviMoon")
    hashtags_line = " ".join(hashtag_list)

    prompt=f"""You are MoviMoon curator. Theme: {genre_cfg['title']} - {industry_cfg['desc']}

EXACT FORMAT FOR 4 MOVIES:

🍿 MoviMoon Movie Picks: {genre_cfg['title']} - {industry_cfg['desc']}

{genre_cfg['desc']}

🎬 1. Movie Name (Year)
⭐ IMDb Rating: X.X/10
📺 OTT Platform: Check MoviMoon.Online
🎭 Movie Type: {genre_cfg['title']}
📅 Release Year: Year
💡 Highlight: [2 sentences in Bengali/Bangla, unique for this movie, based on overview, exciting, spoiler-free]

(Repeat for 2,3,4)

👉 দুর্দান্ত সব মুভি/সিরিজ দেখতে বা ডাউনলোড করতে এখনি গুগলে সার্চ করুন বা সরাসরি ভিজিট করুন MoviMoon.Online ।

Hashtags:
{hashtags_line}

RULES:
- ONLY 4 movies
- Each Highlight MUST be Bengali and UNIQUE, based on overview
- OTT ALWAYS Check MoviMoon.Online
- CTA exact

Data: {json.dumps(movie_data, ensure_ascii=False)}
"""

    text_result=""
    if client and GEMINI_OK:
        try:
            for model_name in ["gemini-3.5-flash-lite","gemini-2.5-flash-lite","gemini-2.0-flash-lite","gemini-2.0-flash","gemini-1.5-flash-8b","gemini-flash-latest"]:
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

    if not text_result:
        def make_bengali_highlight(overview, title, genre_title):
            overview = overview.lower()
            gt = genre_title.lower()
            if "action" in gt:
                return f"{title} তে বিস্ফোরক অ্যাকশন ও রোমাঞ্চে ভরপুর এক দুর্ধর্ষ যাত্রা। শ্বাসরুদ্ধকর স্টান্ট আর লড়াই আপনাকে শেষ পর্যন্ত বুঁদ করে রাখবে।"
            elif "horror" in gt:
                return f"{title} এর ভয়ংকর আতঙ্কে আপনার রক্ত হিম হয়ে যাবে। অন্ধকারে লুকিয়ে থাকা আতঙ্কের মুখোমুখি হতে প্রস্তুত তো?"
            elif "thriller" in gt:
                return f"{title} এর টানটান উত্তেজনায় প্রতি মুহূর্তে নতুন মোড়। শেষ পর্যন্ত কে অপরাধী তা জানতে আপনাকে চোখ রাখতেই হবে।"
            elif "sci-fi" in gt or "sci_fi" in overview:
                return f"{title} তে ভবিষ্যতের প্রযুক্তি ও মহাকাশের রহস্যে ভরা এক অবিশ্বাস্য সফর। বাস্তবতা ও কল্পনার সীমা মুছে যাবে।"
            elif "crime" in gt:
                return f"{title} এর অপরাধ জগতের অন্ধকার কাহিনী। পুলিশ আর অপরাধীর ইঁদুর-বিড়াল খেলায় কে জিতবে?"
            elif "comedy" in gt:
                return f"{title} দেখে হাসতে হাসতে পেটে ব্যথা হয়ে যাবে। বন্ধুদের সাথে দেখার জন্য পারফেক্ট কমেডি।"
            elif "romance" in gt:
                return f"{title} এর মিষ্টি প্রেমের গল্পে মন ভরে যাবে। ভালোবাসার উত্থান-পতনের এক হৃদয়ছোঁয়া কাহিনী।"
            else:
                return f"{title} এর অসাধারণ গল্পে রহস্য, আবেগ ও উত্তেজনা ভরপুর। শেষ পর্যন্ত চোখ সরাতে পারবেন না।"

        lines=[f"🍿 MoviMoon Movie Picks: {genre_cfg['title']} - {industry_cfg['desc']}", "", genre_cfg['desc'], ""]
        for i, md in enumerate(movie_data,1):
            unique_highlight = make_bengali_highlight(md.get('overview',''), md['name'], genre_cfg['title'])
            lines.append(f"🎬 {i}. {md['name']} ({md['year']})")
            lines.append(f"⭐ IMDb Rating: {md['rating']}/10")
            lines.append(f"📺 OTT Platform: Check MoviMoon.Online")
            lines.append(f"🎭 Movie Type: {genre_cfg['title']}")
            lines.append(f"📅 Release Year: {md['year']}")
            lines.append(f"💡 Highlight: {unique_highlight}")
            lines.append("")
        lines.append("👉 দুর্দান্ত সব মুভি/সিরিজ দেখতে বা ডাউনলোড করতে এখনি গুগলে সার্চ করুন বা সরাসরি ভিজিট করুন MoviMoon.Online ।")
        lines.append("")
        lines.append("Hashtags:")
        lines.append(hashtags_line)
        text_result="\n".join(lines)

    text_result = re.sub(r"📺 OTT Platform:.*", "📺 OTT Platform: Check MoviMoon.Online", text_result, flags=re.IGNORECASE)
    cta="👉 দুর্দান্ত সব মুভি/সিরিজ দেখতে বা ডাউনলোড করতে এখনি গুগলে সার্চ করুন বা সরাসরি ভিজিট করুন MoviMoon.Online ।"
    if cta not in text_result:
        if "Hashtags:" in text_result:
            text_result = text_result.replace("Hashtags:", f"{cta}\n\nHashtags:")
        else:
            text_result+=f"\n\n{cta}"
    if "Hashtags:" in text_result:
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
    print(f"Slot {slot} {slot_cfg['bd_time']} Pool {slot_cfg['pool']} Industries {slot_cfg['industries']}")
    genre_key=random.choice(slot_cfg['pool'])
    industry_key=random.choice(slot_cfg['industries'])
    genre_cfg=GENRES[genre_key]
    industry_cfg=INDUSTRY_CONFIG[industry_key]
    print(f"V5 Selected ORIGINAL: {genre_cfg['title']} (ID:{genre_cfg['id']}) | Industry: {industry_cfg['desc']} | Lang: {industry_cfg['lang']}")

    history=load_history()
    candidates=fetch_tmdb_pure_genre(genre_key, industry_key, count=4)
    
    fresh=[]
    for m in candidates:
        if not is_posted(m['id'], history, days=60):
            fresh.append(m)
        if len(fresh)>=4:
            break
    
    if len(fresh) < 4:
        print(f"Only {len(fresh)} fresh, filling")
        seen_ids = set([f['id'] for f in fresh])
        for m in candidates:
            if m['id'] not in seen_ids:
                fresh.append(m)
                seen_ids.add(m['id'])
            if len(fresh)>=4:
                break

    if len(fresh) < 4:
        print(f"❌ Not enough {len(fresh)} for {genre_key} {industry_key}, trying fallback industry")
        # Fallback to hollywood if bollywood fails
        if industry_key != "hollywood":
            candidates2 = fetch_tmdb_pure_genre(genre_key, "hollywood", count=4)
            for m in candidates2:
                if m['id'] not in [f['id'] for f in fresh]:
                    fresh.append(m)
                if len(fresh)>=4:
                    break
        if len(fresh) < 4:
            print(f"❌ Still not enough, abort")
            return

    unique_ids = set()
    final_fresh=[]
    for m in fresh[:4]:
        if m['id'] not in unique_ids:
            final_fresh.append(m)
            unique_ids.add(m['id'])
    fresh = final_fresh

    if len(fresh) < 4:
        print(f"❌ Duplicate IDs")
        return

    print(f"Final 4 V5 ORIGINAL:")
    for i,m in enumerate(fresh,1):
        print(f"{i}. {m.get('title') or m.get('name')} ({(m.get('release_date') or m.get('first_air_date') or '')[:4]}) ID:{m['id']} Lang:{m.get('original_language')} Industry:{m.get('_industry')}")

    posters=download_posters(fresh)
    if len(posters) != 4:
        print(f"❌ Poster download failed")
        return

    collage=create_2x2_grid_with_center_watermark(posters, WATERMARK_FILE, "merged_post.jpg")
    if not collage:
        print("Collage failed")
        return

    caption=generate_caption_gemini_4movies(fresh, genre_cfg, industry_cfg)
    print(f"\n=== CAPTION V5 ===\n{caption[:1500]}...\n")

    fb=post_to_facebook(collage, caption)
    if fb:
        print(f"✅ POSTED V5 SUCCESS: {fb.get('id')} | {genre_cfg['title']} - {industry_cfg['desc']}")
        for m in fresh:
            history[str(m['id'])]=datetime.now().isoformat()
        save_history(history)
    else:
        print("❌ FB post failed")

    for f in posters+[collage]:
        try: Path(f).unlink()
        except: pass

if __name__=="__main__":
    main()
