#!/usr/bin/env python3
"""YouTube Audio Scraper - Extract audio from YouTube videos and save as MP3 with metadata."""

import argparse
import os
import sys
import tempfile
import requests
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from mutagen.id3 import ID3, APIC, TIT2, TPE1
from tqdm import tqdm


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
            return parsed.netloc in ["youtube.com", "www.youtube.com", "youtu.be", "www.youtu.be"]
        except Exception:
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
                        "preferredquality": "320",
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
                    print(f"Downloading: {url}")
                    info = ydl.extract_info(url, download=True)
                    metadata = {
                        "title": info.get("title", "Unknown"),
                        "artist": info.get("uploader", "Unknown"),
                        "thumbnail": info.get("thumbnail"),
                    }

                # Find the converted MP3 file
                mp3_files = list(Path(temp_dir).glob("*.mp3"))
                if not mp3_files:
                    raise RuntimeError("No MP3 file generated")

                source_mp3 = mp3_files[0]
                output_filename = f"{metadata['title']}.mp3"
                # Sanitize filename
                output_filename = "".join(c for c in output_filename if c.isalnum() or c in " ._-")
                output_path = self.output_dir / output_filename

                # Move file to output directory
                source_mp3.rename(output_path)
                return str(output_path), metadata

            except yt_dlp.utils.DownloadError as e:
                raise RuntimeError(f"Failed to download video: {e}")

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
            print("Download complete, converting to MP3...")

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
            if metadata.get("thumbnail"):
                try:
                    self._add_cover_art(id3, metadata["thumbnail"])
                except Exception as e:
                    print(f"Warning: Could not add cover art: {e}")

            id3.save(mp3_path, v2_version=3)
            print(f"Metadata added: Title='{metadata.get('title')}', Artist='{metadata.get('artist')}'")

        except Exception as e:
            raise RuntimeError(f"Failed to add metadata: {e}")

    def _add_cover_art(self, id3, thumbnail_url: str):
        """Download and add cover art from thumbnail URL."""
        response = requests.get(thumbnail_url, timeout=10, stream=True)
        response.raise_for_status()

        # Get content length for progress bar
        total_size = int(response.headers.get("content-length", 0))

        # Download with progress bar if size is known
        if total_size > 0:
            pbar = tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                desc="Downloading cover art",
                leave=False,
            )
            content = b""
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    content += chunk
                    pbar.update(len(chunk))
            pbar.close()
        else:
            content = response.content

        # Add cover art as APIC frame
        id3.add(
            APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,  # Cover (front)
                desc="Cover",
                data=content,
            )
        )

    def scrape(self, url: str) -> str:
        """Main scrape method: download audio and add metadata."""
        try:
            output_path, metadata = self.download_audio(url)
            self.add_metadata(output_path, metadata)
            print(f"✓ Saved to: {output_path}")
            return output_path
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
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

    args = parser.parse_args()

    scraper = YouTubeAudioScraper(output_dir=args.output_dir)
    scraper.scrape(args.url)


if __name__ == "__main__":
    main()
