#!/usr/bin/env python3
"""YouTube Audio Scraper - Extract audio from YouTube videos and save as MP3 with metadata."""

import argparse
import json
import logging
import os
import re
import sys
import tempfile
import requests
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import yt_dlp
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TYER, TXXX, COMM, WOAR

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


class MetadataEditor:
    """Handle interactive metadata editing and custom tagging rules."""

    @staticmethod
    def interactive_edit(metadata: dict) -> dict:
        """
        Prompt user to interactively edit metadata fields.
        Returns modified metadata dictionary.
        """
        print("\n" + "=" * 60)
        print("METADATA EDITOR - Press Enter to skip a field")
        print("=" * 60)

        editable_fields = [
            ("title", "Title"),
            ("artist", "Artist/Uploader"),
            ("album", "Album (leave blank to use Artist)"),
            ("year", "Year"),
            ("description", "Description"),
        ]

        for field_key, field_label in editable_fields:
            current_value = metadata.get(field_key, "")
            if not current_value:
                current_value = "(not set)"
                display_value = ""
            else:
                display_value = current_value

            # Truncate long values for display
            if len(str(current_value)) > 60:
                display_current = str(current_value)[:57] + "..."
            else:
                display_current = str(current_value)

            prompt = f"{field_label}\n  Current: {display_current}\n  New value: "
            user_input = input(prompt).strip()

            if user_input:
                metadata[field_key] = user_input
            elif field_key == "album" and user_input == "":
                # Album defaults to artist if left blank
                if metadata.get("artist"):
                    metadata[field_key] = metadata["artist"]

        print("=" * 60 + "\n")
        return metadata

    @staticmethod
    def apply_tagging_rules(metadata: dict, rules: dict) -> dict:
        """
        Apply custom tagging rules to metadata.
        Rules format:
        {
            "album_source": "artist|title|custom:Album Name",
            "artist_prefix": "Prefix - ",
            "title_suffix": " (Audio)",
            "description_template": "{artist} - {title}"
        }
        """
        modified = metadata.copy()

        # Handle album_source rule
        if "album_source" in rules:
            rule = rules["album_source"]
            if rule == "artist":
                modified["album"] = modified.get("artist", "Unknown")
            elif rule == "title":
                modified["album"] = modified.get("title", "Unknown")
            elif rule.startswith("custom:"):
                modified["album"] = rule[7:]  # Remove "custom:" prefix

        # Handle artist_prefix
        if "artist_prefix" in rules and modified.get("artist"):
            modified["artist"] = rules["artist_prefix"] + modified["artist"]

        # Handle title_suffix
        if "title_suffix" in rules and modified.get("title"):
            modified["title"] = modified["title"] + rules["title_suffix"]

        # Handle description_template
        if "description_template" in rules:
            try:
                template = rules["description_template"]
                modified["description"] = template.format(**modified)
            except KeyError as e:
                logging.warning(f"Description template uses unknown field: {e}")

        # Handle year extraction from release_date if year missing
        if "auto_extract_year" in rules and rules["auto_extract_year"]:
            if not modified.get("year") and modified.get("description"):
                # Try to extract a 4-digit year from description
                year_match = re.search(r"\b(19|20)\d{2}\b", modified["description"])
                if year_match:
                    modified["year"] = year_match.group(0)

        return modified

    @staticmethod
    def load_rules_from_file(rules_file: str) -> dict:
        """Load custom tagging rules from JSON file."""
        try:
            with open(rules_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error(f"Rules file not found: {rules_file}")
            return {}
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON in rules file: {rules_file}")
            return {}

    @staticmethod
    def save_rules_to_file(rules: dict, rules_file: str):
        """Save custom tagging rules to JSON file."""
        try:
            with open(rules_file, "w") as f:
                json.dump(rules, f, indent=2)
            logging.info(f"Rules saved to: {rules_file}")
        except Exception as e:
            logging.error(f"Failed to save rules file: {e}")


class YouTubeAudioScraper:
    """Handle YouTube audio extraction and MP3 metadata tagging."""

    def __init__(self, output_dir=None, interactive_edit=False, rules_file=None):
        """Initialize scraper with optional output directory and metadata customization."""
        self.output_dir = Path(output_dir or ".")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = None
        self.postproc_started = False
        self.interactive_edit = interactive_edit
        self.rules_file = rules_file
        self.tagging_rules = {}

        # Load rules if provided
        if rules_file:
            self.tagging_rules = MetadataEditor.load_rules_from_file(rules_file)

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

            # Reset postproc flag for this download
            self.postproc_started = False

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

                    # Extract additional metadata
                    duration = info.get("duration")  # Duration in seconds
                    view_count = info.get("view_count")
                    description = info.get("description", "")

                    # Build video URL
                    video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None

                    metadata = {
                        "title": info.get("title", "Unknown"),
                        "artist": info.get("uploader", "Unknown"),
                        "thumbnail": thumbnail_url,
                        "year": year,
                        "duration": duration,
                        "view_count": view_count,
                        "description": description,
                        "video_url": video_url,
                        "video_id": video_id,
                    }

                # Find the converted MP3 file
                mp3_files = list(Path(temp_dir).glob("*.mp3"))
                if not mp3_files:
                    raise RuntimeError("No MP3 file generated")

                source_mp3 = mp3_files[0]
                # Use YouTube video title as filename, preserving special characters
                output_filename = f"{metadata['title']}.mp3"
                # Sanitize filename to remove only truly invalid characters
                output_filename = self._sanitize_filename(output_filename)
                output_path = self.output_dir / output_filename

                # Move file to output directory
                source_mp3.rename(output_path)
                return str(output_path), metadata

            except yt_dlp.utils.DownloadError as e:
                logger.error(f"Failed to download video: {e}")
                raise RuntimeError(f"Failed to download video: {e}")

    def _progress_hook(self, d: dict):
        """Progress hook for yt-dlp downloads and postprocessing."""
        if d["status"] == "downloading":
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded_bytes = d.get("downloaded_bytes", 0)

            if total_bytes > 0:
                percentage = (downloaded_bytes / total_bytes) * 100
                # Display progress with visual bar
                bar_length = 40
                filled = int(bar_length * downloaded_bytes / total_bytes)
                bar = "█" * filled + "░" * (bar_length - filled)
                print(
                    f"\rDownloading: |{bar}| {percentage:.1f}%",
                    end="",
                    flush=True,
                )

        elif d["status"] == "finished":
            print()  # Newline after progress bar

        elif d["status"] == "processing":
            # Show postprocessor progress
            if not self.postproc_started:
                print()  # Newline before processing message
                self.postproc_started = True

            postprocessor = d.get("postprocessor", "FFmpeg")
            print(f"\rProcessing: Converting to MP3 ({postprocessor})...", end="", flush=True)

        elif d["status"] == "postprocess-progress":
            # Some postprocessors provide detailed progress
            if not self.postproc_started:
                print()
                self.postproc_started = True

            maxHookLines = d.get("maxHookLines", 0)
            if maxHookLines > 0:
                percent = d.get("index", 0) / maxHookLines * 100
                bar_length = 40
                filled = int(bar_length * percent / 100)
                bar = "█" * filled + "░" * (bar_length - filled)
                print(
                    f"\rProcessing: |{bar}| {percent:.1f}%",
                    end="",
                    flush=True,
                )

    @staticmethod
    def _format_duration(duration_seconds: int) -> str:
        """Format duration in seconds to HH:MM:SS format."""
        if not duration_seconds:
            return "0:00"
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        r"""
        Sanitize filename by removing only truly invalid characters.
        Preserves special characters like: - _ () [] {} & + = etc.
        Only removes: / \ : * ? " < > |
        """
        # Characters that are invalid in filenames on most filesystems
        invalid_chars = r'[\/<>:*?"|\x00-\x1f]'
        sanitized = re.sub(invalid_chars, "", filename)
        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip(". ")
        # Collapse multiple spaces into one
        sanitized = re.sub(r"\s+", " ", sanitized)
        return sanitized

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

            # Add title (iTunes compatible)
            if metadata.get("title"):
                id3.add(TIT2(encoding=3, text=metadata["title"]))

            # Add artist (iTunes compatible)
            if metadata.get("artist"):
                id3.add(TPE1(encoding=3, text=metadata["artist"]))

            # Add album as uploader name by default, or custom album if provided (iTunes compatible)
            album = metadata.get("album") or metadata.get("artist", "Unknown")
            if album:
                id3.add(TALB(encoding=3, text=album))

            # Add year using standard TYER frame (iTunes compatible)
            if metadata.get("year"):
                id3.add(TYER(encoding=3, text=metadata["year"]))

            # Add description/comments (iTunes compatible)
            if metadata.get("description"):
                id3.add(COMM(encoding=3, lang="eng", desc="", text=metadata["description"]))

            # Add video URL/webpage (iTunes may or may not display)
            if metadata.get("video_url"):
                id3.add(WOAR(url=metadata["video_url"]))

            # Add view count as custom tag (iTunes won't display, but stored in file)
            if metadata.get("view_count"):
                id3.add(TXXX(encoding=3, desc="View Count", text=str(metadata["view_count"])))

            # Add duration as custom tag (iTunes won't display, but stored in file)
            if metadata.get("duration"):
                duration_str = self._format_duration(metadata["duration"])
                id3.add(TXXX(encoding=3, desc="Duration", text=duration_str))

            # Add cover art if thumbnail available
            cover_added = False
            if metadata.get("thumbnail"):
                try:
                    self._add_cover_art(id3, metadata["thumbnail"])
                    cover_added = True
                except Exception as e:
                    logger.warning(f"Could not add cover art: {e}")

            id3.save(mp3_path, v2_version=3)

            # Build detailed metadata info for logging
            metadata_parts = [f"Title='{metadata.get('title')}'", f"Artist='{metadata.get('artist')}'"]

            if metadata.get('year'):
                metadata_parts.append(f"Year='{metadata.get('year')}'")
            if metadata.get('view_count'):
                metadata_parts.append(f"Views={metadata.get('view_count'):,}")
            if metadata.get('duration'):
                duration_str = self._format_duration(metadata.get('duration'))
                metadata_parts.append(f"Duration='{duration_str}'")
            if metadata.get('video_url'):
                metadata_parts.append("URL: Added")
            if metadata.get('description'):
                metadata_parts.append("Description: Added")
            if cover_added:
                metadata_parts.append("Cover: Yes")

            logger.info(f"Metadata added: {', '.join(metadata_parts)}")

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

            # Apply custom tagging rules if available
            if self.tagging_rules:
                logger.info("Applying custom tagging rules...")
                metadata = MetadataEditor.apply_tagging_rules(metadata, self.tagging_rules)

            # Interactive metadata editing if enabled
            if self.interactive_edit:
                metadata = MetadataEditor.interactive_edit(metadata)

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
    parser.add_argument("url", nargs="?", help="YouTube URL to scrape")
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
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Enable interactive metadata editing before saving",
    )
    parser.add_argument(
        "-r",
        "--rules",
        dest="rules_file",
        help="Path to JSON file with custom tagging rules",
    )
    parser.add_argument(
        "--save-rules",
        dest="save_rules_file",
        help="Save a template rules file to the specified path",
    )

    args = parser.parse_args()

    # Set logging level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # Handle --save-rules template generation
    if args.save_rules_file:
        template_rules = {
            "album_source": "artist",
            "artist_prefix": "",
            "title_suffix": "",
            "description_template": "{artist} - {title}",
            "auto_extract_year": False,
        }
        MetadataEditor.save_rules_to_file(template_rules, args.save_rules_file)
        logger.info(f"Template rules file created: {args.save_rules_file}")
        logger.info("Edit this file to customize metadata tagging rules")
        return

    # URL is required if not using --save-rules
    if not args.url:
        parser.error("URL argument is required (unless using --save-rules)")

    scraper = YouTubeAudioScraper(
        output_dir=args.output_dir,
        interactive_edit=args.interactive,
        rules_file=args.rules_file,
    )
    scraper.scrape(args.url)


if __name__ == "__main__":
    main()
