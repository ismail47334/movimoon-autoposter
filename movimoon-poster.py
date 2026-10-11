import os
import requests
import random
import re
from datetime import datetime

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
    # Mix of movie and tv trending
    url = f"https://api.themoviedb.org/3/trending/all/day?api_key={TMDB_API_KEY}&language=en-US"
    r = requests.get(url, timeout=15).json()
    results = [m for m in r.get("results", []) if m.get("poster_path") and m.get("id")]
    # Ensure mix: try to get at least 1 tv and 1 movie if possible
    random.shuffle(results)
    return results[:3]

def build_movimoon_link(movie):
    tmdb_id = movie.get("id")
    title = movie.get("title") or movie.get("name") or "untitled"
    slug = slugify(title)
    media_type = movie.get("media_type")
    # media_type from trending is 'movie' or 'tv'
    if media_type == "tv":
        return f"https://movimoon.online/tv/{tmdb_id}-{slug}", media_type
    else:
        return f"https://movimoon.online/movie/{tmdb_id}-{slug}", "movie"

def generate_bangla_caption(movie, link):
    title = movie.get("title") or movie.get("name")
    rating = round(movie.get("vote_average", 0), 1)
    release = movie.get("release_date") or movie.get("first_air_date") or ""
    year = release[:4] if release else "2025"
    overview_en = movie.get("overview","")[:400]
    media_type = movie.get("media_type", "movie")
    genres = "Trending" # TMDB trending doesn't give genre names directly without extra call, we keep simple

    # Gemini Optimized Prompt for movimoon.online
    if GEMINI_API_KEY:
        try:
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
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
   CTA Example: "ফুল রিভিউ, কাস্ট, ট্রেলার আর ডাউনলোড লিংক একসাথে দেখো এখানে 👉 {link}"
8. Hashtags: #MoviMoon #TrendingNow #{slugify(title).replace('-','')} #BanglaReview
9. NEVER say "Free streaming on MoviMoon", "Watch free on MoviMoon". Say "রিভিউ/ডিটেলস দেখো" - MoviMoon is info/review site.
10. NO spoilers. Total 130-170 words.

OUTPUT: Only final post text.
"""
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(gemini_url, json=payload, timeout=25).json()
            review_text = res['candidates'][0]['content']['parts'][0]['text']
            # Ensure link is present (Gemini sometimes skips)
            if link not in review_text:
                review_text += f"\n\n👉 বিস্তারিত দেখো: {link}"
            return review_text.strip()
        except Exception as e:
            print(f"Gemini error: {e}")

    # Fallback template (if Gemini fails)
    templates = [
        f"🔥 {title} এখন ট্রেন্ডিং কাঁপাচ্ছে!\n{title} ({year}) | {media_type.upper()} | ⭐ {rating}/10\n\n{overview_en[:150]}... গল্পের বিল্ড-আপ অসাধারণ, শেষ ২০ মিনিটে এমন টুইস্ট আছে যে মাথা ঘুরে যাবে। তবে মাঝের কিছু সিন একটু স্লো লাগতে পারে।\n\nযারা থ্রিলার লাভার তাদের জন্য মাস্ট ওয়াচ।\nতোমার কেমন লাগলো? কমেন্টে জানাও!\n\n👉 ফুল রিভিউ, কাস্ট, ট্রেলার দেখো MoviMoon এ: {link}\n\n#MoviMoon #TrendingNow #BanglaReview",
    ]
    return random.choice(templates)

def post_to_facebook(page_id, token, image_url, caption):
    url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
    data = {"url": image_url, "caption": caption, "access_token": token}
    r = requests.post(url, data=data, timeout=30)
    print(f"PAGE POST {page_id}: {r.status_code} {r.text[:300]}")
    return r

def main():
    items = get_trending_mixed()
    print(f"Found {len(items)} trending items")
    for movie in items:
        poster_url = f"https://image.tmdb.org/t/p/w780{movie['poster_path']}"
        link, m_type = build_movimoon_link(movie)
        caption = generate_bangla_caption(movie, link)
        print(f"\n--- Posting {movie.get('title') or movie.get('name')} -> {link} ---")
        print(caption)
        if FB_PAGE_ID and FB_PAGE_TOKEN:
            post_to_facebook(FB_PAGE_ID, FB_PAGE_TOKEN, poster_url, caption)
        if FB_GROUP_ID and FB_PAGE_TOKEN:
            post_to_facebook(FB_GROUP_ID, FB_PAGE_TOKEN, poster_url, caption)

if __name__ == "__main__":
    main()
