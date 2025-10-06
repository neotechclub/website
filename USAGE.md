# NeoTech Club Website - Usage Guide

## Installation

### 1. Install Pixi (Linux/macOS)

```bash
curl -fsSL https://pixi.sh/install.sh | sh
```

For other platforms, visit: https://pixi.sh/

### 2. Install Dependencies

```bash
pixi install
```

This will install all required dependencies (Python, PyYAML, etc.) automatically.

## Building the Website

### Development Mode (Build + Run Server)

```bash
pixi run dev
```

This will:
1. Build the website (convert YAML to JSON, minify files)
2. Start a local HTTP server on port 8080
3. Open http://localhost:8080 in your browser

### Build Only (Generate `out/` folder)

```bash
pixi run build
```

Or directly:

```bash
python build.py
```

This generates the production-ready files in the `out/` folder.

## Project Structure

```
website/
├── index.html              # Main page with all sections
├── past-events.html        # Past events page
├── events.yaml             # Event data (with dates, signup URLs)
├── schedule.yaml           # Weekly schedule data
├── build.py                # Build script
├── donotbuild.yaml         # Build exclusions config
└── out/                    # Generated output (deploy this!)
    ├── index.html          # Minified
    ├── past-events.html    # Minified
    ├── events.json         # Sorted by date
    └── schedule.json       # Clean schedule data
```

## Editing Content

### Adding Events

Edit `events.yaml`:

```yaml
current_events:
  - title: "Your Event Name"
    date: "TBA"  # or YYYY-MM-DD
    description: "Event description"
    location: "Lab"
    duration: "1 hour"
    border_color: "amber"  # or "cyan", "green"
    signup_url: "https://forms.gle/your-form"
    instructions_url: "/your-instructions.pdf"

past_events:
  - title: "Past Event"
    date: "2025-09-15"  # YYYY-MM-DD format (sorted newest first)
    description: "What happened"
    location: "Lab"
```

### Updating Schedule

Edit `schedule.yaml`:

```yaml
schedule:
  - title: "Activity Name"
    frequency: "Twice weekly"
    activities:
      - duration: "15 min"
        description: "What you do"
```

**Note**: Schedule does NOT have signup/instructions URLs. Those are only for events.

## Build Process

The build script (`build.py`) automatically:

1. **Converts YAML to JSON**
   - `events.yaml` → `events.json` (past events sorted newest first)
   - `schedule.yaml` → `schedule.json`

2. **Minifies Files**
   - HTML files (removes whitespace, preserves `<pre>` tags)
   - CSS files (removes comments, whitespace)
   - JS files (removes comments, extra whitespace)

3. **Respects Exclusions**
   - Skips files listed in `donotbuild.yaml`
   - Default exclusions: `*.yaml`, `*.yml`, `build.py`, etc.

## Deployment

Deploy the contents of the `out/` folder to your web server:

```bash
# Example: rsync to server
rsync -av out/ user@server:/var/www/html/

# Or copy to nginx/apache web root
cp -r out/* /var/www/html/
```

## Features

### Contact Section
- XMPP, Telegram, WhatsApp, Email, In-Person
- NO GitHub or Matrix links

### Events
- Current events: Shows latest 3 at runtime
- Each event has signup & instructions links
- Past events: Separate page, sorted by date (newest first)

### Schedule
- Weekly rhythm only
- NO signup/instructions (those are per-event)

### Mobile
- Responsive navigation with hamburger menu
- Touch-friendly interface

### Blog
- Links to `/blog` (external)
- RSS copy button: `https://neotechclub.qzz.io/blog/post/index.xml`

### Join Section
- Temporary Member vs Full Member
- Google Forms apology with degoogle option

## Troubleshooting

### Build fails
```bash
# Check if pixi is installed
pixi --version

# Reinstall dependencies
pixi install --force
```

### Server won't start
```bash
# Check if port 8080 is in use
lsof -i :8080

# Use different port
python -m http.server 3000 -d out/
```

### JavaScript not working
- Make sure you're viewing the built version in `out/`
- Check browser console for errors
- Rebuild: `pixi run build`

## Development Tips

- Edit source files (`index.html`, `*.yaml`), NOT files in `out/`
- Run `pixi run build` after changes
- The build script preserves formatting in `<pre>` tags
- Bootstrap icons load from CDN (no local files needed)

## License

GPL-3.0 License

---

**Questions?** Check the project repository or contact the club directly.
