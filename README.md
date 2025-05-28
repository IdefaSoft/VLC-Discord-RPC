# VLC-Discord-RPC

Display your currently playing VLC music as Discord Rich Presence (with artwork support)

## Features

- 🎵 **Real-time status updates** - Shows currently playing track, artist, and album
- 🖼️ **Artwork display** - Uploads and displays album artwork in Discord
- ⏱️ **Progress tracking** - Shows elapsed time and remaining time
- 🎮 **Play/Pause states** - Different icons for playing and paused states
- 🔄 **Smart caching** - Caches artwork to improve performance
- 🎛️ **Auto-detection** - Automatically reads VLC web interface configuration
- 📁 **Audio file filtering** - Only shows presence for audio files (MP3, FLAC, WAV, OGG, AAC, OPUS)

## Prerequisites

- Python 3.9+
- VLC Media Player **with web interface enabled**
- Discord Desktop

## VLC Setup

1. Open VLC Media Player
2. Go to `Tools` → `Preferences`
3. In the bottom left, select `All` under "Show settings"
4. Navigate to `Interface` → `Main interfaces`
5. Check `Web` to enable the web interface
6. Go to `Interface` → `Main interfaces` → `Lua`
   - Set a password in the `Lua HTTP` → `Password` field
   - Click `Save`
7. Restart VLC

## Installation

### Basic Setup
1. Clone or download the repository
2. Install required dependencies:
   ```bash
   pip install requests
   ```

### Optional: Artwork Server Setup
For album artwork support, you can run the included Flask server:

1. **Configure the artwork server:**
   ```python
   # In server.py, set your public domain or IP address
   BASE_URL = 'http://X.X.X.X:PORT'
   ```

2. **Install Dependencies:**
   ```bash
    pip install Flask flask_limiter
    ```

3. **Run the artwork server:**
   ```bash
   python server.py
   ```

4. **Update the main script:**
   ```python
   # In main.py, set your server endpoint
   ARTWORK_API_ENDPOINT = "http://X.X.X.X:PORT/upload"
   ```

## Usage

1. Start VLC Media Player with web interface enabled, and start Discord
2. Run the Python script
3. Play any audio file in VLC
4. Your Discord status will update automatically

The presence will show:
- **Song title** as the main activity
- **Artist name** as the state
- **Album artwork** as the large image
- **Play/pause status** as the small image
- **Progress bar** with remaining time

Disclaimer: This program may contain bugs. I've only tested it on Windows, so it may not work on other operating systems. If you encounter any issues, feel free to open an issue.