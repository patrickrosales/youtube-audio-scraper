# YouTube Audio Scraper

A command-line tool to extract audio from YouTube videos and save as MP3 files with ID3 metadata tags and cover art.

## Features

- 🎵 Extract audio from YouTube videos in MP3 format
- 📝 Automatic ID3 metadata tagging (title, artist/uploader)
- 🖼️ Downloads and embeds video thumbnail as cover art
- 📊 Real-time progress bar during download/conversion
- 🛡️ URL validation and comprehensive error handling
- 🚀 Fast and efficient using yt-dlp and FFmpeg

## Requirements

- Python 3.7+
- FFmpeg (for audio conversion)
- Internet connection

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/youtube-audio-scraper.git
cd youtube-audio-scraper
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Install FFmpeg (if not already installed):

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt-get install ffmpeg
```

**Windows:**
```bash
choco install ffmpeg
```

## Usage

### Basic Usage

Download audio from a YouTube video:
```bash
python youtube_scraper.py "https://www.youtube.com/watch?v=..."
```

### Specify Output Directory

Save the MP3 to a specific directory:
```bash
python youtube_scraper.py "https://www.youtube.com/watch?v=..." -o ./music
```

### Command-Line Options

```
positional arguments:
  url                   YouTube URL to scrape

optional arguments:
  -h, --help            Show this help message and exit
  -o, --output OUTPUT   Output directory for MP3 files (default: current directory)
```

## Examples

```bash
# Download and save to current directory
python youtube_scraper.py "https://youtu.be/dQw4w9WgXcQ"

# Save to a custom folder
python youtube_scraper.py "https://youtu.be/dQw4w9WgXcQ" -o ~/Music

# Long-form YouTube URL
python youtube_scraper.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s" -o ./downloads
```

## Output

The tool will:
1. Download the best available audio quality
2. Convert to MP3 (192 kbps)
3. Extract video metadata (title, uploader)
4. Download video thumbnail and embed as cover art
5. Save the file with ID3 tags to your output directory

Example output:
```
Downloading: https://youtu.be/dQw4w9WgXcQ
Downloading: |████████████████████████████████████████| 100.0%
Download complete, converting to MP3...
Metadata added: Title='Video Title', Artist='Channel Name'
✓ Saved to: ./Video Title.mp3
```

## Troubleshooting

### HTTP Error 403: Forbidden

This typically means YouTube has blocked yt-dlp due to signature extraction issues.

**Solution:** Update yt-dlp to the latest version:
```bash
pip install --upgrade yt-dlp
```

YouTube frequently updates their access controls. If the error persists, try using browser cookies for authentication.

### FFmpeg Not Found

Ensure FFmpeg is installed and accessible from your PATH. Test with:
```bash
ffmpeg -version
```

### "Invalid YouTube URL"

Ensure you're using a valid YouTube URL format:
- ✓ `https://www.youtube.com/watch?v=...`
- ✓ `https://youtu.be/...`
- ✗ `youtube.com/watch?v=...` (missing protocol)

### Age-Restricted or Private Videos

Public videos work without authentication. For age-restricted content, you may need to provide browser cookies.

## Dependencies

- **yt-dlp** - YouTube video downloader
- **mutagen** - Audio metadata (ID3 tags)
- **requests** - HTTP library for downloading cover art
- **tqdm** - Progress bar display

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
