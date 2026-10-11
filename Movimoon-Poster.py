import os
import requests
import random
from datetime import datetime

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
FB_GROUP_ID = os.getenv("FB_GROUP_ID")  # optional
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # optional, fallback to template

def get_trending_movies():
    url = f"https://api.themoviedb.org/3/trending/all/day?api_key={TMDB_API_KEY}&language=en-US"
    r = requests.get(url).json()
    results = r.get("results", [])
    # filter only good quality with poster
    filtered = [m for m in results if m.get("poster_path") and m.get("vote_average",0) >= 5]
    return random.sample(filtered, min(3, len(filtered)))

def generate_bangla_caption(movie, use_gemini=True):
    title = movie.get("title") or movie.get("name")
    rating = movie.get("vote_average", 0)
    release = movie.get("release_date") or movie.get("first_air_date") or ""
    overview_en = movie.get("overview","")[:300]
    media_type = movie.get("media_type","movie")
    
    # Slug for movimoon.online link
    slug = title.lower().replace(" ", "-").replace(":", "").replace("'", "")
    site_link = f"https://movimoon.online/{media_type}/{slug}"

    # Try Gemini for real bangla review
    if use_gemini and GEMINI_API_KEY:
        try:
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            prompt = f"""You are writing for movimoon.online facebook page.
            Write a short, spicy 70-80 word Bangla review for this trending {media_type}: {title} ({release}).
            Info: {overview_en}. Rating {rating}.
            Rules: Use colloquial Bangla + 1-2 emoji, make it exciting, mention why people should watch now.
            End with a CTA to watch on movimoon.online.
            Don't include link, I will add it. Only return review text."""
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(gemini_url, json=payload, timeout=20).json()
            review = res['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            print(f"Gemini failed: {e}, using template")
            review = None
    else:
        review = None

    if not review:
        templates = [
            f"🔥 আজকের ট্রেন্ডিং কাঁপাচ্ছে {title}! ⭐ রেটিং {rating}/10। গল্পটা এমনভাবে টানবে যে এক বসায় শেষ না করে উঠতেই পারবে না। টুইস্ট আর অ্যাকশন দুটোই আছে ভরপুর।",
            f"🎬 {title} এখন ট্রেন্ডিং #1 এ! যারা {media_type} লাভার, তাদের জন্য মাস্ট ওয়াচ। শেষ ২০ মিনিটে এমন টুইস্ট আছে যে মাথা ঘুরে যাবে।",
            f"💥 ভাই {title} কি জিনিস বানাইছে! IMDb {rating} এমনি এমনি দেয়নি। ফ্যামিলি নিয়ে দেখার মতো একটা কন্টেন্ট, বোর হওয়ার চান্স নেই।"
        ]
        review = random.choice(templates)

    caption = f"""{review}

🎭 নাম: {title}
⭐ রেটিং: {rating}/10
📅 রিলিজ: {release}
🎬 ধরন: {media_type.upper()}

👉 ফুল HD তে দেখুন ও ডাউনলোড করুন এখানে:
{site_link}

#Movimoon #TrendingNow #{title.replace(' ','')} #BanglaReview #NewMovie
"""
    return caption, site_link

def post_to_facebook(page_id, token, image_url, caption):
    url = f"https://graph.facebook.com/{page_id}/photos"
    data = {
        "url": image_url,
        "caption": caption,
        "access_token": token
    }
    r = requests.post(url, data=data)
    print(f"Page Post: {r.status_code} - {r.text}")
    return r.json()

def post_to_group(group_id, token, image_url, caption):
    if not group_id:
        return
    # Group needs app installed in group
    url = f"https://graph.facebook.com/{group_id}/photos"
    data = {
        "url": image_url,
        "caption": caption,
        "access_token": token
    }
    r = requests.post(url, data=data)
    print(f"Group Post: {r.status_code} - {r.text}")

def main():
    movies = get_trending_movies()
    for movie in movies:
        poster_url = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
        caption, link = generate_bangla_caption(movie)
        print(f"Posting: {movie.get('title') or movie.get('name')}")
        post_to_facebook(FB_PAGE_ID, FB_PAGE_TOKEN, poster_url, caption)
        if FB_GROUP_ID:
            post_to_group(FB_GROUP_ID, FB_PAGE_TOKEN, poster_url, caption)

if __name__ == "__main__":
    main()
