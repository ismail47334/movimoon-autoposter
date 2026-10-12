import os, requests, random, re, time

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
FB_GROUP_ID = os.getenv("FB_GROUP_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text).strip('-')
    return text[:60]

def get_trending_mixed():
    url = f"https://api.themoviedb.org/3/trending/all/day?api_key={TMDB_API_KEY}&language=en-US"
    r = requests.get(url, timeout=15).json()
    results = [m for m in r.get("results", []) if m.get("poster_path") and m.get("id")]
    random.shuffle(results)
    return results[:3]

def build_movimoon_link(movie):
    tmdb_id = movie.get("id")
    title = movie.get("title") or movie.get("name") or "untitled"
    slug = slugify(title)
    media_type = movie.get("media_type")
    if media_type == "tv":
        return f"https://movimoon.online/tv/{tmdb_id}-{slug}", media_type
    else:
        return f"https://movimoon.online/movie/{tmdb_id}-{slug}", "movie"

def call_gemini_master(title, year, media_type, rating, overview_en, link):
    hashtag = slugify(title).replace('-','')
    prompt = f"""
You are MoviMoon.online Senior Movie Reviewer. Write ONE viral Facebook post in colloquial natural Bengali.

INPUT:
Title: {title} ({year})
Type: {media_type} - Use 'সিনেমা' for movie, 'সিরিজ' for tv
Rating: {rating}/10
Overview: {overview_en}
MoviMoon Link: {link}

RULES:
1. Hook: First line must be super catchy with 1 emoji, max 12 words. Different each time.
2. Second line: {title} ({year}) | {media_type.upper()} | ⭐ {rating}/10
3. Then 80-100 words spoiler-free Bengali review. Must include 1 specific strength (acting/VFX/story) + 1 honest limitation. Talk like a real Bengali movie buff friend, use words like 'ভাই', 'মাস্ট ওয়াচ', 'এক বসায় শেষ'.
4. Language: Pure natural Bengali (mix English movie terms ok).
5. Who should watch: 1 line.
6. Discussion question at end to get comments.
7. CTA must use this EXACT link: {link} - Do not modify link.
8. Hashtags: #MoviMoon #TrendingNow #{hashtag} #BanglaReview
9. NEVER say "Free streaming on MoviMoon". Say "রিভিউ/ডিটেলস দেখো"
10. NO spoilers. Total 130-170 words.
OUTPUT: Only final post text.
"""
    models = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-flash-latest"]
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.95, "maxOutputTokens": 700}}
            res = requests.post(url, json=payload, timeout=30).json()
            if "candidates" in res and res["candidates"]:
                parts = res["candidates"][0].get("content", {}).get("parts", [])
                text = "".join([p.get("text","") for p in parts if "text" in p]).strip()
                if text:
                    print(f"Gemini success with {model}")
                    if link not in text:
                        text += f"\n\n👉 ফুল রিভিউ, কাস্ট, ট্রেলার দেখো MoviMoon এ: {link}"
                    return text
            print(f"Gemini {model} failed: {str(res)[:400]}")
        except Exception as e:
            print(f"Gemini {model} error: {e}")
    return None

def generate_caption(movie, link):
    title = movie.get("title") or movie.get("name")
    rating = round(movie.get("vote_average", 0), 1)
    release = movie.get("release_date") or movie.get("first_air_date") or ""
    year = release[:4] if release else "2025"
    overview_en = movie.get("overview","")[:400]
    media_type = movie.get("media_type", "movie")
    result = call_gemini_master(title, year, media_type, rating, overview_en, link) if GEMINI_API_KEY else None
    if result:
        return result
    return f"🔥 {title} নিয়ে আলোচনা তুঙ্গে!\n{title} ({year}) | {media_type.upper()} | ⭐ {rating}/10\n\n{overview_en[:120]}... এক বসায় শেষ করার মতো গল্প।\n\n👉 ফুল রিভিউ, কাস্ট, ট্রেলার দেখো MoviMoon এ: {link}\n\n#MoviMoon #TrendingNow #BanglaReview"

def post_to_facebook(target_id, token, image_url, caption, label):
    url = f"https://graph.facebook.com/v19.0/{target_id}/photos"
    data = {"url": image_url, "caption": caption, "access_token": token}
    r = requests.post(url, data=data, timeout=30)
    print(f"{label} {target_id}: {r.status_code} {r.text[:500]}")
    return r

def main():
    items = get_trending_mixed()
    print(f"Found {len(items)} items")
    for movie in items:
        poster_url = f"https://image.tmdb.org/t/p/w780{movie['poster_path']}"
        link, m_type = build_movimoon_link(movie)
        caption = generate_caption(movie, link)
        print(f"\n--- {movie.get('title') or movie.get('name')} -> {link} ---")
        # 1. Post to Page
        if FB_PAGE_ID and FB_PAGE_TOKEN:
            post_to_facebook(FB_PAGE_ID, FB_PAGE_TOKEN, poster_url, caption, "PAGE POST")
        # 2. Post to Group using SAME Page Token (Page is Admin of Group, no publish_to_groups needed)
        if FB_GROUP_ID and FB_PAGE_TOKEN:
            time.sleep(2)
            post_to_facebook(FB_GROUP_ID, FB_PAGE_TOKEN, poster_url, caption, "GROUP POST")
        time.sleep(1)

if __name__ == "__main__":
    main()
