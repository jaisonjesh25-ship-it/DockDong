import subprocess
import urllib.request
import urllib.parse
import json
import os
import time
import re
import glob
import logging

APP = "spotify"  # "spotify" or "apple_music"
CHECK_INTERVAL = 5
COVER_DIR = os.path.expanduser("~/Pictures/MusicWallpaperChanger")


def get_now_playing(app):
    app_name = "Spotify" if app == "spotify" else "Music"

    script = f'''
    tell application "{app_name}"
        if player state is playing then
            set trackName to name of current track
            set artistName to artist of current track
            set albumName to album of current track
            return trackName & "|||" & artistName & "|||" & albumName
        else
            return "NOT_PLAYING"
        end if
    end tell
    '''

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )

        output = result.stdout.strip()

        if output == "NOT_PLAYING" or not output:
            return None, None, None

        parts = output.split("|||")

        if len(parts) == 3:
            return parts[0].strip(), parts[1].strip(), parts[2].strip()

    except Exception as e:
        logging.error(f"[Music App] Error: {e}", exc_info=True)

    return None, None, None


def clean(text):
    text = text.lower()
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\bfeat\.?\b.*", "", text)
    text = re.sub(r"\bft\.?\b.*", "", text)
    text = re.sub(r"\bwith\b.*", "", text)

    remove_words = [
        "deluxe",
        "remastered",
        "edition",
        "version",
        "bonus",
        "expanded",
        "anniversary",
        "remaster",
        "special",
        "explicit",
    ]

    for word in remove_words:
        text = re.sub(rf"\b{word}\b", "", text)

    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def words(text):
    ignored = {"a", "an", "and", "by", "of", "the"}
    return {word for word in clean(text).split() if word not in ignored}


def overlap_ratio(left, right):
    if not left or not right:
        return 0

    return len(left & right) / max(len(left), len(right))


def score_match(result, artist, album, track):
    r_artist = clean(result.get("artistName") or "")
    r_album = clean(result.get("collectionName") or "")

    c_artist = clean(artist or "")
    c_album = clean(album or "")

    r_artist_words = words(result.get("artistName") or "")
    r_album_words = words(result.get("collectionName") or "")

    c_artist_words = words(artist)
    c_album_words = words(album)

    score = 0

    if c_artist == r_artist:
        score += 70
    elif c_artist and r_artist and (c_artist in r_artist or r_artist in c_artist):
        score += 45
    else:
        score += int(overlap_ratio(c_artist_words, r_artist_words) * 40)

    if c_album == r_album:
        score += 85
    elif c_album and r_album and (c_album in r_album or r_album in c_album):
        score += 55
    else:
        score += int(overlap_ratio(c_album_words, r_album_words) * 65)

    if c_album_words and not (c_album_words & r_album_words):
        score -= 70

    if c_artist_words and not (c_artist_words & r_artist_words):
        score -= 45

    if r_artist == "various artists" and c_artist != r_artist:
        score -= 60

    if result.get("collectionType") == "Album":
        score += 10

    raw_name = (result.get("collectionName") or "").lower()

    wanted_single = "single" in album.lower()
    wanted_ep = re.search(r"\bep\b", album.lower()) is not None

    if " - single" in raw_name and not wanted_single:
        score -= 40

    if (" - ep" in raw_name or raw_name.endswith(" ep") or " ep)" in raw_name) and not wanted_ep:
        score -= 40

    bad_words = [
        "b-sides",
        "b sides",
        "remix",
        "remixes",
        "live",
        "instrumental",
        "karaoke",
        "tribute",
        "covers",
    ]

    if any(word in raw_name for word in bad_words) and c_album not in clean(raw_name):
        score -= 35

    if c_album == r_album:
        score += 30

    track_count = result.get("trackCount", 0)

    if track_count and track_count >= 8:
        score += 5

    return score


def fetch_album_art(track, artist, album):
    all_results = []

    queries = [
        f"{artist} {album}",
        f"{album} {artist}",
        f"{artist} {album} album",
        f"{track} {artist} {album}",
    ]

    for query in queries:
        params = urllib.parse.urlencode(
            {
                "term": query,
                "media": "music",
                "entity": "album",
                "limit": 15,
            }
        )

        url = f"https://itunes.apple.com/search?{params}"

        try:
            with urllib.request.urlopen(url, timeout=8) as response:
                data = json.loads(response.read().decode())
                all_results.extend(data.get("results", []))
        except Exception as e:
            logging.error(f"[iTunes] Search error: {e}", exc_info=True)

    if not all_results:
        return None

    seen = set()
    unique = []

    for result in all_results:
        collection_id = result.get("collectionId")

        if collection_id and collection_id not in seen:
            seen.add(collection_id)
            unique.append(result)

    scored = [(score_match(result, artist, album, track), result) for result in unique]
    scored.sort(key=lambda item: item[0], reverse=True)

    if not scored:
        return None

    best_score, best = scored[0]

    if best_score < 65:
        return None

    art_url = best.get("artworkUrl100", "")

    if art_url:
        return art_url.replace("100x100bb", "3000x3000bb")

    return None


def download_image(url, save_path):
    try:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        urllib.request.urlretrieve(url, save_path)
        return True
    except Exception as e:
        logging.error(f"[Download] Error: {e}", exc_info=True)

    return False


def cleanup_old_covers(keep_path=None):
    for old_file in glob.glob(os.path.join(COVER_DIR, "music_cover_*.jpg")):
        if keep_path and os.path.abspath(old_file) == os.path.abspath(keep_path):
            continue

        try:
            os.remove(old_file)
        except Exception:
            pass


def update_wallpaper_once(app=APP, last_track=None):
    track, artist, album = get_now_playing(app)

    if track is None:
        return {"status": "not_playing", "last_track": last_track}

    if not (track and artist and album):
        return {"status": "missing_metadata", "last_track": last_track}

    if track == last_track:
        return {"status": "unchanged", "last_track": last_track}

    art_url = fetch_album_art(track, artist, album)

    if not art_url:
        return {
            "status": "no_art",
            "last_track": last_track,
            "track": track,
            "artist": artist,
            "album": album,
        }

    timestamp = int(time.time())
    save_path = os.path.join(COVER_DIR, f"music_cover_{timestamp}.jpg")

    if not download_image(art_url, save_path):
        cleanup_old_covers()
        return {
            "status": "download_failed",
            "last_track": last_track,
            "track": track,
            "artist": artist,
            "album": album,
        }

    if not set_wallpaper(save_path):
        cleanup_old_covers()
        return {
            "status": "wallpaper_failed",
            "last_track": last_track,
            "track": track,
            "artist": artist,
            "album": album,
        }

    cleanup_old_covers(keep_path=save_path)

    return {
        "status": "updated",
        "last_track": track,
        "track": track,
        "artist": artist,
        "album": album,
        "image_path": save_path,
    }


def set_wallpaper(image_path):
    abs_path = os.path.abspath(image_path)

    if not os.path.exists(abs_path):
        return False

    apple_path = abs_path.replace("\\", "\\\\").replace('"', '\\"')

    scripts = [
        f'''
        tell application "System Events"
            repeat with d in desktops
                set picture of d to "{apple_path}"
            end repeat
        end tell
        ''',
        f'''
        tell application "Finder"
            set desktop picture to POSIX file "{apple_path}"
        end tell
        ''',
    ]

    for script in scripts:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            subprocess.run(
                ["killall", "Dock"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return True

    return False


def run_wallpaper_changer():
    last_track = None

    while True:
        result = update_wallpaper_once(APP, last_track)
        last_track = result.get("last_track", last_track)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run_wallpaper_changer()
