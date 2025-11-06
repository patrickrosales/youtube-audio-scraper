#!/usr/bin/env python3
"""YouTube Audio Scraper - Extract audio from YouTube videos and save as MP3 with metadata."""

import argparse
import logging
import os
import sys
import tempfile
import requests
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import yt_dlp
from mutagen.id3 import ID3, APIC, TIT2, TPE1
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_AUDIO_BITRATE = 320
THUMBNAIL_CHUNK_SIZE = 8192
THUMBNAIL_TIMEOUT = 10


class YouTubeAudioScraper:
    """Handle YouTube audio extraction and MP3 metadata tagging."""

    def __init__(self, output_dir=None):
        """Initialize scraper with optional output directory."""
        self.output_dir = Path(output_dir or ".")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = None
        self.pbar = None

    def validate_youtube_url(self, url: str) -> bool:
        """Validate that the URL is a YouTube URL."""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()

            # Check for standard YouTube domains
            is_youtube_domain = netloc in [
                "youtube.com",
                "www.youtube.com",
                "youtu.be",
                "www.youtu.be",
                "m.youtube.com",  # Mobile YouTube
                "youtube-nocookie.com",
                "www.youtube-nocookie.com",
            ]

            if not is_youtube_domain:
                return False

            # Verify there's a path or video ID
            if not parsed.path and not parsed.query:
                return False

            return True
        except Exception:
            logger.debug(f"URL validation error for: {url}", exc_info=True)
            return False

    def download_audio(self, url: str) -> tuple[str, dict]:
        """
        Download audio from YouTube using yt-dlp.
        Returns tuple of (output_path, metadata_dict).
        """
        if not self.validate_youtube_url(url):
            raise ValueError(f"Invalid YouTube URL: {url}")

        # Use temp directory for temporary files
        with tempfile.TemporaryDirectory() as temp_dir:
            output_template = os.path.join(temp_dir, "%(title)s.%(ext)s")

            ydl_opts = {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": DEFAULT_AUDIO_BITRATE,
                    }
                ],
                "outtmpl": output_template,
                "quiet": False,
                "no_warnings": False,
                "progress_hooks": [self._progress_hook],
            }

            metadata = {}

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info(f"Downloading: {url}")
                    info = ydl.extract_info(url, download=True)

                    # Extract year from upload_date or release_date
                    year = None
                    if info.get("upload_date"):
                        # upload_date is in YYYYMMDD format
                        year = info.get("upload_date")[:4]
                    elif info.get("release_date"):
                        # release_date is in YYYY-MM-DD format
                        year = info.get("release_date").split("-")[0]

                    # Get video ID for consistent thumbnail URL
                    video_id = info.get("id")
                    # YouTube thumbnail URL format: https://img.youtube.com/vi/VIDEO_ID/maxresdefault.jpg
                    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg" if video_id else None

                    metadata = {
                        "title": info.get("title", "Unknown"),
                        "artist": info.get("uploader", "Unknown"),
                        "thumbnail": thumbnail_url,
                        "year": year,
                    }

                # Find the converted MP3 file
                mp3_files = list(Path(temp_dir).glob("*.mp3"))
                if not mp3_files:
                    raise RuntimeError("No MP3 file generated")

                source_mp3 = mp3_files[0]
                # Include year in filename if available
                if metadata["year"]:
                    output_filename = f"{metadata['title']} ({metadata['year']}).mp3"
                else:
                    output_filename = f"{metadata['title']}.mp3"
                # Sanitize filename
                output_filename = "".join(c for c in output_filename if c.isalnum() or c in " ()._-")
                output_path = self.output_dir / output_filename

                # Move file to output directory
                source_mp3.rename(output_path)
                return str(output_path), metadata

            except yt_dlp.utils.DownloadError as e:
                logger.error(f"Failed to download video: {e}")
                raise RuntimeError(f"Failed to download video: {e}")

    @contextmanager
    def _progress_bar(self, total: int, desc: str = "Progress"):
        """Context manager for progress bar lifecycle."""
        pbar = tqdm(
            total=total,
            unit="B",
            unit_scale=True,
            desc=desc,
            leave=True,
        )
        try:
            yield pbar
        finally:
            pbar.close()

    def _progress_hook(self, d: dict):
        """Progress hook for yt-dlp downloads."""
        if d["status"] == "downloading":
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded_bytes = d.get("downloaded_bytes", 0)

            if total_bytes > 0:
                # Initialize progress bar on first update
                if self.pbar is None:
                    self.pbar = tqdm(
                        total=total_bytes,
                        unit="B",
                        unit_scale=True,
                        desc="Downloading",
                        leave=True,
                    )

                # Update progress bar
                delta = downloaded_bytes - self.pbar.n
                if delta > 0:
                    self.pbar.update(delta)

        elif d["status"] == "finished":
            if self.pbar is not None:
                self.pbar.close()
                self.pbar = None
            logger.info("Download complete, converting to MP3...")

    def add_metadata(self, mp3_path: str, metadata: dict):
        """Add ID3 tags and cover art to MP3 file."""
        try:
            # Remove existing ID3 tags
            try:
                id3 = ID3(mp3_path)
                id3.delete()
            except:
                pass

            # Create new ID3 tags
            id3 = ID3()

            # Add title
            if metadata.get("title"):
                id3.add(TIT2(encoding=3, text=metadata["title"]))

            # Add artist
            if metadata.get("artist"):
                id3.add(TPE1(encoding=3, text=metadata["artist"]))

            # Add cover art if thumbnail available
            cover_added = False
            if metadata.get("thumbnail"):
                try:
                    self._add_cover_art(id3, metadata["thumbnail"])
                    cover_added = True
                except Exception as e:
                    logger.warning(f"Could not add cover art: {e}")

            id3.save(mp3_path, v2_version=3)
            year_info = f", Year='{metadata.get('year')}'" if metadata.get('year') else ""
            cover_info = ", Cover: Yes" if cover_added else ""
            logger.info(f"Metadata added: Title='{metadata.get('title')}', Artist='{metadata.get('artist')}'{year_info}{cover_info}")

        except Exception as e:
            logger.error(f"Failed to add metadata: {e}")
            raise RuntimeError(f"Failed to add metadata: {e}")

    def _add_cover_art(self, id3, thumbnail_url: str):
        """Download and add cover art from thumbnail URL."""
        # Try maxresdefault first, fall back to other qualities if needed
        thumbnail_urls = [
            thumbnail_url,  # maxresdefault (original)
            thumbnail_url.replace("maxresdefault", "sddefault"),  # 640x480
            thumbnail_url.replace("maxresdefault", "hqdefault"),  # 480x360
            thumbnail_url.replace("maxresdefault", "default"),    # 120x90
        ]

        content = None
        for url in thumbnail_urls:
            try:
                response = requests.get(url, timeout=THUMBNAIL_TIMEOUT, stream=True)
                response.raise_for_status()

                # Get content length for progress bar
                total_size = int(response.headers.get("content-length", 0))

                # Download with progress bar if size is known
                if total_size > 0:
                    with self._progress_bar(total_size, desc="Downloading cover art") as pbar:
                        content = b""
                        for chunk in response.iter_content(chunk_size=THUMBNAIL_CHUNK_SIZE):
                            if chunk:
                                content += chunk
                                pbar.update(len(chunk))
                else:
                    content = response.content

                if content:
                    logger.debug(f"Successfully downloaded thumbnail from {url}")
                    break
            except Exception as e:
                logger.debug(f"Failed to download from {url}: {e}")
                continue

        if not content:
            raise RuntimeError("Failed to download thumbnail from all available URLs")

        # Add cover art as APIC frame with empty description for better compatibility
        id3.add(
            APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,  # Cover (front)
                desc="",  # Empty description for better player compatibility
                data=content,
            )
        )

    def scrape(self, url: str) -> str:
        """Main scrape method: download audio and add metadata."""
        try:
            output_path, metadata = self.download_audio(url)
            self.add_metadata(output_path, metadata)
            logger.info(f"✓ Saved to: {output_path}")
            return output_path
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            sys.exit(1)
        except RuntimeError as e:
            logger.error(f"Runtime error: {e}")
            sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract audio from YouTube videos and save as MP3 with metadata."
    )
    parser.add_argument("url", help="YouTube URL to scrape")
    parser.add_argument(
        "-o",
        "--output",
        dest="output_dir",
        default=".",
        help="Output directory for MP3 files (default: current directory)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging output",
    )

    args = parser.parse_args()

    # Set logging level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    scraper = YouTubeAudioScraper(output_dir=args.output_dir)
    scraper.scrape(args.url)


if __name__ == "__main__":
    main()
