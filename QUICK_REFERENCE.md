# Metadata Customization - Quick Reference

## The Basics

### Interactive Editing
Edit metadata one field at a time before saving:
```bash
python3 youtube_scraper.py <URL> --interactive
```

### Custom Rules Files
Apply automatic transformations using a JSON rules file:
```bash
# Create a template
python3 youtube_scraper.py --save-rules my_rules.json

# Use your rules
python3 youtube_scraper.py <URL> --rules my_rules.json

# Or both together
python3 youtube_scraper.py <URL> --rules my_rules.json --interactive
```

## Rules Quick Reference

Create a `rules.json` file and customize:

```json
{
  "album_source": "artist",           // Where album comes from
  "artist_prefix": "",                // Add prefix to artist
  "title_suffix": "",                 // Add suffix to title
  "description_template": "",         // Template for description
  "auto_extract_year": false          // Extract year from description
}
```

### album_source Options
- `"artist"` → Use artist/uploader name
- `"title"` → Use video title
- `"custom:Album Name"` → Fixed custom name

### Template Variables
Use `{field_name}` in description template:
- `{title}`, `{artist}`, `{album}`, `{year}`
- `{duration}`, `{view_count}`, `{video_id}`, `{video_url}`

## Common Patterns

### Music Channel
```json
{
  "album_source": "artist",
  "title_suffix": " (Audio)"
}
```

### Podcast
```json
{
  "album_source": "custom:My Podcast",
  "artist_prefix": "Ep. "
}
```

### Lectures
```json
{
  "album_source": "artist",
  "title_suffix": " [Lecture]",
  "description_template": "{artist} - {title}\nVideo: {video_url}"
}
```

## Interactive Mode Tips

Press **Enter** to keep current value
Type new value to override
Album will default to artist if left blank

## File Locations

Save rules files anywhere and reference with:
```bash
python3 youtube_scraper.py <URL> --rules /path/to/rules.json
```

For persistent setup, create `my_rules.json` in your working directory.
