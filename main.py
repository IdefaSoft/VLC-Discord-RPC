import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

import requests

from rpc import DiscordRPC, Activity, ActivityType, Timestamp, Asset

CLIENT_ID = "1376645197450055691"

ARTWORK_API_ENDPOINT = "" # Set this to your server's public URL. If left empty, it will use the default artwork
CACHE_FILE = Path(__file__).parent / "artwork_cache.json"

AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.ogg', '.aac', '.opus'}
DEFAULT_ARTWORK = "vlc_logo"
UPDATE_INTERVAL = 5

artwork_cache: dict[str, str] = {}


def log(message: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def load_cache() -> None:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r', encoding="utf-8") as f:
                artwork_cache.update(json.load(f))
        except json.JSONDecodeError:
            log(f"Error loading cache file {CACHE_FILE}. It may be corrupted.")


def save_cache() -> None:
    try:
        with open(CACHE_FILE, 'w', encoding="utf-8") as f:
            json.dump(artwork_cache, f)
    except Exception as e:
        log(f"Error saving cache file {CACHE_FILE}: {e}")


def get_file_hash(file_path: str) -> str:
    try:
        stat = os.stat(file_path)
        cache_string = f"{os.path.basename(file_path)}:{stat.st_size}:{stat.st_mtime}"
        return hashlib.md5(cache_string.encode('utf-8')).hexdigest()
    except Exception as e:
        log(f"Error getting file info {file_path}: {e}")
        return ""


def upload_artwork(artwork_path: str) -> str:
    if not ARTWORK_API_ENDPOINT or not artwork_path:
        return DEFAULT_ARTWORK

    try:
        artwork_path = unquote(artwork_path.replace('file:///', '', 1))
        if not os.path.isfile(artwork_path):
            return DEFAULT_ARTWORK

        file_hash = get_file_hash(artwork_path)
        if file_hash in artwork_cache:
            return artwork_cache[file_hash]
        elif file_hash == "":
            return DEFAULT_ARTWORK

        with open(artwork_path, 'rb') as img_file:
            files = {'file': img_file}
            response = requests.post(ARTWORK_API_ENDPOINT, files=files, timeout=10)

        if response.status_code == 200:
            url = response.json().get('url')
            if url:
                artwork_cache[file_hash] = url
                save_cache()
                return url
    except Exception as e:
        log(f"Error uploading artwork: {e}")

    return DEFAULT_ARTWORK


def get_vlc_web_interface_config() -> tuple[str, str, str]:
    config = {'host': '127.0.0.1', 'port': '8080', 'password': ''}

    if os.name == 'nt':
        vlc_config_path = Path(os.environ.get('APPDATA', '')) / 'vlc' / 'vlcrc'
    else:
        vlc_config_path = Path.home() / '.config' / 'vlc' / 'vlcrc'
    if not vlc_config_path.exists():
        return config['host'], config['port'], config['password']

    with open(vlc_config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    for key in ['host', 'port', 'password']:
        match = re.search(rf'^http-{key}=(.+)', content, re.MULTILINE)
        if match:
            config[key] = match.group(1).strip()

    return config['host'], config['port'], config['password']


def fetch_vlc_status(host: str, port: str, password: str) -> tuple[Optional[dict], Optional[str]]:
    url = f"http://{host}:{port}/requests/status.json"
    auth = ('', password) if password else None

    try:
        response = requests.get(url, auth=auth, timeout=5)
        response.raise_for_status()
        return response.json(), None

    except requests.exceptions.ConnectionError:
        return None, "Could not connect to VLC web interface"
    except requests.exceptions.Timeout:
        return None, "Request timed out while connecting to VLC"
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return None, "Authentication failed"
        else:
            return None, f"HTTP {e.response.status_code} - {e.response.reason}"
    except Exception as e:
        return None, str(e)


def is_audio_file(status: dict) -> bool:
    if not (filename := status.get('information', {}).get('category', {}).get('meta', {}).get('filename')):
        return False

    file_extension = os.path.splitext(filename)[1].lower()
    return file_extension in AUDIO_EXTENSIONS


def extract_media_info(status: dict) -> tuple[str, str, str, int, int, bool, str]:
    meta = status.get('information', {}).get('category', {}).get('meta', {})

    title = meta.get('title', 'Unknown Title')
    artist = meta.get('artist', 'Unknown Artist')
    album = meta.get('album', '')
    artwork_url = meta.get('artwork_url', '')

    if title == 'Unknown Title' and 'filename' in meta:
        filename = os.path.basename(meta['filename'])
        name, _ = os.path.splitext(filename)

        if ' - ' in name:
            parts = name.split(' - ', 1)
            if artist == 'Unknown Artist':
                artist = parts[0]
            title = parts[1]
        else:
            title = name

    length = int(status.get('length', 0))
    time_position = int(status.get('time', 0))
    is_playing = status.get('state') == 'playing'

    return title, artist, album, length, time_position, is_playing, artwork_url


def create_discord_activity(media_info: tuple[str, str, str, int, int, bool, str]) -> Activity:
    title, artist, album, length, position, is_playing, artwork_url = media_info

    timestamps = None
    if is_playing and length > 0:
        current_time = int(time.time())
        start_time = current_time - position
        end_time = start_time + length
        timestamps = Timestamp(start=start_time, end=end_time)

    assets = Asset(
        large_image=upload_artwork(artwork_url),
        large_text=album if album else "No Album",
        small_image="playing" if is_playing else "paused",
        small_text="Playing" if is_playing else "Paused"
    )

    activity = Activity(
        details=title,
        state=artist,
        activity_type=ActivityType.LISTENING,
        timestamps=timestamps,
        assets=assets
    )

    return activity


def update_discord_presence(rpc: DiscordRPC, vlc_config: tuple[str, str, str]) -> Optional[str]:
    host, port, password = vlc_config

    status, error = fetch_vlc_status(host, port, password)
    if error:
        rpc.clear_activity()
        return f"Failed to fetch VLC status: {error}"

    state = status.get('state')
    if state not in ['playing', 'paused'] or not is_audio_file(status):
        rpc.clear_activity()
        return

    media_info = extract_media_info(status)
    activity = create_discord_activity(media_info)

    success = rpc.set_activity(activity.to_dict())
    if not success:
        return "Failed to update Discord rich presence"


def run_discord_rpc(client_id: str, update_interval: int) -> None:
    rpc = DiscordRPC(client_id)
    vlc_config = get_vlc_web_interface_config()
    load_cache()

    if not rpc.connect():
        log("Failed to connect to Discord")
        return

    log("Connected to Discord RPC")
    log(f"Monitoring VLC at {vlc_config[0]}:{vlc_config[1]}")

    try:
        while True:
            error = update_discord_presence(rpc, vlc_config)
            if error:
                log(error)

            time.sleep(update_interval)
    except KeyboardInterrupt:
        log("Shutting down...")
    finally:
        rpc.clear_activity()
        rpc.disconnect()
        log("Disconnected from Discord")


if __name__ == "__main__":
    run_discord_rpc(CLIENT_ID, UPDATE_INTERVAL)
