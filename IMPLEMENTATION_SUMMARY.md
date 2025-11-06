# Metadata Customization Feature - Implementation Summary

## Overview
Successfully implemented comprehensive metadata customization for the YouTube Audio Scraper, allowing users to override extracted metadata and apply custom tagging rules without manually editing files.

## Features Added

### 1. MetadataEditor Class
New class in `youtube_scraper.py` (lines 32-151) with three main capabilities:

- **`interactive_edit(metadata)`** - Interactive CLI prompts to edit metadata fields
  - Allows editing: Title, Artist, Album, Year, Description
  - Shows current values with truncation for long fields
  - Defaults album to artist if left blank
  
- **`apply_tagging_rules(metadata, rules)`** - Automatically transform metadata
  - `album_source`: Set album from artist, title, or custom value
  - `artist_prefix`: Prepend text to artist name
  - `title_suffix`: Append text to title
  - `description_template`: Generate descriptions using field variables
  - `auto_extract_year`: Extract year from description if not set

- **`load_rules_from_file(rules_file)`** - Load JSON rules files
- **`save_rules_to_file(rules, rules_file)`** - Save rules templates

### 2. YouTubeAudioScraper Updates
Modified initialization and scrape flow:

- Added `interactive_edit` and `rules_file` parameters to `__init__`
- Auto-loads rules from file if provided
- Integrated into scrape workflow:
  1. Download audio
  2. Apply tagging rules (if provided)
  3. Show interactive editor (if enabled)
  4. Add metadata to MP3

### 3. CLI Extensions
New command-line arguments:

- `-i, --interactive` - Enable interactive metadata editing
- `-r, --rules RULES_FILE` - Path to custom tagging rules JSON
- `--save-rules SAVE_RULES_FILE` - Generate template rules file

### 4. Album Metadata Handling
Updated `add_metadata()` method (line 389):
- Now respects custom album metadata
- Falls back to artist if album not provided
- Maintains ID3 compatibility

## Usage Examples

### Interactive Mode
```bash
python3 youtube_scraper.py "https://www.youtube.com/watch?v=..." --interactive
```

### Custom Rules
```bash
# Generate template
python3 youtube_scraper.py --save-rules my_rules.json

# Use rules
python3 youtube_scraper.py "https://www.youtube.com/watch?v=..." --rules my_rules.json
```

### Combined
```bash
python3 youtube_scraper.py "https://www.youtube.com/watch?v=..." \
  --rules my_rules.json \
  --interactive
```

## Example Rules Files

### Music Archive
```json
{
  "album_source": "artist",
  "artist_prefix": "",
  "title_suffix": " (YouTube Audio)",
  "description_template": "{artist} - {title} (Year: {year})",
  "auto_extract_year": true
}
```

### Podcast Organization
```json
{
  "album_source": "custom:My Podcast",
  "artist_prefix": "Episode ",
  "title_suffix": "",
  "description_template": "{title} - {artist}",
  "auto_extract_year": false
}
```

## Documentation
Created `METADATA_CUSTOMIZATION.md` with:
- Interactive editing guide
- Complete tagging rules reference
- Available metadata fields
- Multiple real-world examples
- Troubleshooting tips

## Testing
- ✓ Code compiles without syntax errors
- ✓ Help menu displays new options correctly
- ✓ Template rule generation works
- ✓ CLI argument parsing handles optional URL correctly
- ✓ JSON loading/saving functions work

## Files Modified
- `youtube_scraper.py` - Added MetadataEditor class, updated YouTubeAudioScraper, enhanced CLI

## Files Created
- `METADATA_CUSTOMIZATION.md` - Complete user documentation

## Backward Compatibility
✓ All changes are backward compatible
- Existing command usage works unchanged
- New features are optional
- No breaking changes to existing behavior

## Code Quality
- Type hints included
- Comprehensive error handling
- Logging throughout for debugging
- Clean separation of concerns
- Well-documented docstrings
