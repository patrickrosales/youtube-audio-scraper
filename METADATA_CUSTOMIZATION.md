# Metadata Customization Guide

The YouTube Audio Scraper now supports advanced metadata customization with two approaches:

## 1. Interactive Metadata Editing

Enable real-time editing of metadata fields after download but before saving:

```bash
python3 youtube_scraper.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --interactive
```

This prompts you to edit:
- **Title** - Video title
- **Artist/Uploader** - Channel name
- **Album** - Album name (defaults to artist if blank)
- **Year** - Release year
- **Description** - Video description

Example workflow:
```
============================================================
METADATA EDITOR - Press Enter to skip a field
============================================================

Title
  Current: Never Gonna Give You Up (Rick Roll)
  New value: Never Gonna Give You Up - Rick Astley

Artist/Uploader
  Current: Rick Astley
  New value:

Album (leave blank to use Artist)
  Current: Rick Astley
  New value: Whenever You Need Somebody

Year
  Current: 1987
  New value:

Description
  Current: The official video for "Never Gonna Give You Up" by Rick Astley...
  New value:

============================================================
```

## 2. Custom Tagging Rules

Use a JSON rules file to automatically transform metadata without manual editing:

### Generate a Template Rules File

```bash
python3 youtube_scraper.py --save-rules my_rules.json
```

This creates a file with all available rules:

```json
{
  "album_source": "artist",
  "artist_prefix": "",
  "title_suffix": "",
  "description_template": "{artist} - {title}",
  "auto_extract_year": false
}
```

### Apply Custom Rules

```bash
python3 youtube_scraper.py "https://www.youtube.com/watch?v=..." --rules my_rules.json
```

### Available Rules

#### `album_source`
Determines where the album tag gets its value:
- `"artist"` - Use artist/uploader name (default)
- `"title"` - Use video title
- `"custom:Album Name"` - Use a fixed custom album name

Examples:
```json
{
  "album_source": "artist"          // Album = Artist name
}
{
  "album_source": "title"           // Album = Video title
}
{
  "album_source": "custom:My Music" // Album = "My Music"
}
```

#### `artist_prefix`
Prepend text to the artist field:

```json
{
  "artist_prefix": "[Podcast] "     // "Rick Astley" → "[Podcast] Rick Astley"
}
```

#### `title_suffix`
Append text to the title field:

```json
{
  "title_suffix": " (Audio)"        // "Song Title" → "Song Title (Audio)"
}
```

#### `description_template`
Template string for generating description using other metadata fields.

Supports any field in metadata with `{field_name}` syntax:
- `{title}`, `{artist}`, `{album}`, `{year}`, `{duration}`, `{view_count}`, `{video_id}`, `{video_url}`

Examples:
```json
{
  "description_template": "{artist} - {title}"
  // Description = "Rick Astley - Never Gonna Give You Up"
}
{
  "description_template": "{title} from {artist} ({year})"
  // Description = "Never Gonna Give You Up from Rick Astley (1987)"
}
{
  "description_template": "Video: {video_url}\nViews: {view_count}"
}
```

#### `auto_extract_year`
Automatically extract year from description if not set (searches for 4-digit years):

```json
{
  "auto_extract_year": true
}
```

### Complete Rules Examples

**Example 1: Podcast Organization**
```json
{
  "album_source": "custom:My Podcast",
  "artist_prefix": "Ep. ",
  "title_suffix": "",
  "description_template": "{title} - Episode from {artist}",
  "auto_extract_year": false
}
```

**Example 2: Music Archive**
```json
{
  "album_source": "artist",
  "artist_prefix": "",
  "title_suffix": " (YouTube Audio)",
  "description_template": "{artist} - {title} (Year: {year})",
  "auto_extract_year": true
}
```

**Example 3: Lecture Archive**
```json
{
  "album_source": "custom:Lectures",
  "artist_prefix": "",
  "title_suffix": "",
  "description_template": "Lecture: {title}\nChannel: {artist}\nVideo: {video_url}",
  "auto_extract_year": true
}
```

## 3. Combining Interactive and Rules

You can use both together - rules are applied first, then interactive editing allows manual refinement:

```bash
python3 youtube_scraper.py "https://www.youtube.com/watch?v=..." \
  --rules my_rules.json \
  --interactive
```

Workflow:
1. Download audio
2. **Apply custom rules** to metadata
3. **Show interactive editor** with modified metadata
4. Save with final metadata

## Command Reference

```bash
# Interactive editing only
python3 youtube_scraper.py <URL> --interactive

# Rules file only
python3 youtube_scraper.py <URL> --rules <path/to/rules.json>

# Both interactive and rules
python3 youtube_scraper.py <URL> --rules <path/to/rules.json> --interactive

# Generate template rules file
python3 youtube_scraper.py --save-rules <path/to/rules.json>

# With custom output directory
python3 youtube_scraper.py <URL> -o ~/Music --interactive --rules my_rules.json

# Verbose output (for debugging rules)
python3 youtube_scraper.py <URL> --rules my_rules.json --verbose
```

## Metadata Fields Reference

The following fields are available in metadata and can be used in templates:

| Field | Description | Example |
|-------|-------------|---------|
| `title` | Video title | "Never Gonna Give You Up" |
| `artist` | Channel/uploader name | "Rick Astley" |
| `album` | Album name | "Whenever You Need Somebody" |
| `year` | Release year | "1987" |
| `description` | Video description | "The official video..." |
| `duration` | Duration in HH:MM:SS format | "3:32" |
| `view_count` | Total views as number | "1234567890" |
| `video_id` | YouTube video ID | "dQw4w9WgXcQ" |
| `video_url` | Full YouTube video URL | "https://www.youtube.com/watch?v=dQw4w9WgXcQ" |

## Tips

1. **Test Your Rules** - Create a test rules file and try it with a video first
2. **Use Verbose Mode** - Add `-v` flag to see which rules are being applied
3. **Template Variables** - Verify field names exist before using them in templates
4. **Special Characters** - Most special characters in metadata are preserved in filenames
5. **Blank Fields** - Leave values empty in interactive mode to keep current value
6. **Album Defaults** - If album is left blank in interactive mode, it defaults to artist

## Example Use Cases

### Music Channel Archiving
Save each video with consistent album name:
```json
{
  "album_source": "custom:Channel Archive",
  "artist_prefix": "",
  "title_suffix": "",
  "description_template": "From {artist}\nViews: {view_count}"
}
```

### Podcast Management
Organize episodes with numbering:
```json
{
  "album_source": "custom:My Podcast S1",
  "artist_prefix": "Episode ",
  "title_suffix": "",
  "description_template": "{title} - {artist}",
  "auto_extract_year": true
}
```

### Educational Content
Track source and metadata:
```json
{
  "album_source": "artist",
  "artist_prefix": "[Lecture] ",
  "title_suffix": " (Audio Version)",
  "description_template": "From: {artist}\nSource: {video_url}"
}
```
