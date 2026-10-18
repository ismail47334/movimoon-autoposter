#!/usr/bin/env python3
# MoviMoon Video Autoposter - FIXED 2026-10-18 - Bot Detection Bypass

import os, json, time, random, subprocess, requests, re
from pathlib import Path

# CONFIG
TRAILER_FILE = "trailer.mp4"
HISTORY_FILE = "posted_history.json"

def run_cmd(cmd, timeout=90):
    print(f"[CMD] {cmd[:200]}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        tail_out = result.stdout[-500:] if result.stdout else ""
        tail_err = result.stderr[-800:] if result.stderr else ""
        if tail_out: print(f"STDOUT tail: {tail_out}")
        if tail_err: print(f"STDERR tail: {tail_err}")
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        print(f"CMD Exception: {e}")
        return False, "", str(e)

def get_cookie_arg():
    """Return --cookies arg if cookies.txt exists"""
    if Path("cookies.txt").exists() and Path("cookies.txt").stat().st_size > 100:
        print(f"Using cookies.txt - {Path('cookies.txt').stat().st_size} bytes")
        return '--cookies cookies.txt'
    print("No valid cookies.txt")
    return ''

def download_via_ytdlp_fixed(youtube_url, output=TRAILER_FILE):
    """FIXED YT-DLP with proper cookies + PO Token + JS runtime"""
    Path(output).unlink(missing_ok=True)
    cookie_arg = get_cookie_arg()
    deno_path = f"{os.environ.get('HOME','/home/runner')}/.deno/bin/deno"
    
    # FIXED Strategies - 2026 working
    strategies = [
        # S1: Android client + cookies (most stable now)
        f'yt-dlp {cookie_arg} --extractor-args "youtube:player_client=android" -f "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --force-ipv4 --sleep-requests 1',
        
        # S2: Android + Web + Deno JS runtime for PO Token auto-gen (via ejs)
        f'yt-dlp {cookie_arg} --js-runtimes deno:{deno_path} --extractor-args "youtube:player_client=android,web" -f "best[height<=720][ext=mp4]/best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --force-ipv4',
        
        # S3: iOS client (often bypasses bot check)
        f'yt-dlp {cookie_arg} --extractor-args "youtube:player_client=ios" -f "best[height<=720]" -o "{output}" "{youtube_url}" --no-playlist --force-ipv4',
        
        # S4: Web client with pot-bgutil-aas (new method for ejs)
        f'yt-dlp {cookie_arg} --js-runtimes deno:{deno_path} --extractor-args "youtubepot-bgutil-aas:enabled=true;youtube:player_client=web" -f "best[height<=720]" -o "{output}" "{youtube_url}" --no-playlist --force-ipv4',
        
        # S5: Bare minimum without client forcing (lets yt-dlp decide)
        f'yt-dlp {cookie_arg} -f "best[height<=720][ext=mp4]/best" --merge-output-format mp4 -o "{output}" "{youtube_url}" --no-playlist --force-ipv4 --no-warnings',
    ]
    
    for i, cmd in enumerate(strategies, 1):
        print(f"\n[yt-dlp] Trying FIXED Strategy {i}/{len(strategies)}")
        ok, out, err = run_cmd(cmd, timeout=120)
        if ok and Path(output).exists() and Path(output).stat().st_size > 50000:
            size_mb = Path(output).stat().st_size / 1024 / 1024
            print(f"✅ SUCCESS Strategy {i} - {size_mb:.2f} MB")
            return True
        # cleanup partial
        Path(output).unlink(missing_ok=True)
        time.sleep(2)
    
    print("All yt-dlp strategies failed")
    return False

def download_via_cobalt_fixed(youtube_url, output=TRAILER_FILE):
    """FIXED Cobalt - using current working instances 2026"""
    Path(output).unlink(missing_ok=True)
    # Updated list - Oct 2026 working instances
    cobalt_instances = [
        "https://api.cobalt.tools/api/json",
        "https://cobalt-api.mjs.moe/",
        "https://co.wuk.sh/api/json",
    ]
    
    for api in cobalt_instances:
        try:
            print(f"Trying Cobalt: {api}")
            payload = {"url": youtube_url, "vCodec": "h264", "vQuality": "720", "isAudioOnly": False, "filenamePattern": "basic"}
            r = requests.post(api, json=payload, headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=20)
            if r.status_code == 200:
                data = r.json()
                dl_url = data.get("url")
                if dl_url:
                    print(f"Cobalt got URL: {dl_url[:100]}")
                    with requests.get(dl_url, stream=True, timeout=120) as dl:
                        with open(output, 'wb') as f:
                            for chunk in dl.iter_content(1024*1024):
                                if chunk: f.write(chunk)
                    if Path(output).exists() and Path(output).stat().st_size > 50000:
                        print(f"✅ Cobalt SUCCESS {Path(output).stat().st_size/1024/1024:.2f} MB")
                        return True
            else:
                print(f"Cobalt {api} status {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"Cobalt {api} error: {e}")
            continue
    
    return False

def download_via_invidious_fixed(video_id, output=TRAILER_FILE):
    """FIXED Invidious - 2026 working instances"""
    Path(output).unlink(missing_ok=True)
    inv_instances = [
        "https://yewtu.be",
        "https://invidious.namazso.eu",
        "https://inv.tux.pizza",
        "https://yt.artemislena.eu",
    ]
    
    for base in inv_instances:
        try:
            api_url = f"{base}/api/v1/videos/{video_id}"
            print(f"Trying Invidious API: {base} -> {api_url}")
            r = requests.get(api_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                data = r.json()
                formats = data.get("formatStreams", []) + data.get("adaptiveFormats", [])
                # pick 720p mp4
                best = None
                for f in formats:
                    if f.get("container") == "mp4" and f.get("height", 0) <= 720 and f.get("type", "").startswith("video"):
                        if not best or f.get("height", 0) > best.get("height", 0):
                            best = f
                if not best and formats:
                    best = formats[0]
                
                if best and best.get("url"):
                    print(f"Invidious found format: {best.get('height')}p")
                    with requests.get(best["url"], stream=True, timeout=120) as dl:
                        with open(output, 'wb') as f:
                            for chunk in dl.iter_content(1024*1024):
                                if chunk: f.write(chunk)
                    if Path(output).exists() and Path(output).stat().st_size > 50000:
                        print(f"✅ Invidious SUCCESS")
                        return True
            else:
                print(f"Invidious {base} status: {r.status_code}")
        except Exception as e:
            print(f"Invidious {base} error: {e}")
            continue
    return False

def smart_download(youtube_url, output=TRAILER_FILE):
    """Master download with all methods"""
    # extract video id
    m = re.search(r"v=([A-Za-z0-9_-]{11})", youtube_url)
    vid = m.group(1) if m else youtube_url.split("/")[-1]
    
    print(f"\n========== DOWNLOAD START: {vid} ==========")
    
    if download_via_ytdlp_fixed(youtube_url, output):
        return True
    
    print("\n=== COBALT NEW METHOD ===")
    if download_via_cobalt_fixed(youtube_url, output):
        return True
    
    print("\n=== INVIDIOUS/PIPED ===")
    if download_via_invidious_fixed(vid, output):
        return True
    
    print("ALL 3 METHODS FAILED")
    return False

# --- Keep your original main logic below, just replace download call ---
# Example usage in your loop:
# if smart_download(f"https://www.youtube.com/watch?v={video_id}"):
#     # continue to upload to FB etc
# else:
#     print(f"Download failed for {title}, next...")
