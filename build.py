#!/usr/bin/env python3
"""
NeoTech Club Website Build Script
Converts YAML to JSON, minifies HTML/CSS/JS, and outputs to out/ folder.
Generates RSS feeds for current and past events.
Respects exclusions listed in donotbuild.yaml
"""

import os
import re
import io
import json
import yaml
import shutil
import fnmatch
from datetime import datetime, time
try:
    # Python 3.9+
    from zoneinfo import ZoneInfo
except Exception:
    # Fallback placeholder; if zoneinfo missing, use UTC-only behavior
    ZoneInfo = None
from pathlib import Path
from html.parser import HTMLParser
from xml.sax.saxutils import escape


class HTMLMinifier(HTMLParser):
    """Simple HTML minifier that removes unnecessary whitespace but preserves script/style content"""
    def __init__(self):
        super().__init__()
        self.output = io.StringIO()
        self.in_pre = False
        self.in_script = False
        self.in_style = False
    
    def handle_decl(self, decl):
        """Preserve DOCTYPE declaration"""
        self.output.write(f'<!{decl}>')
        
    def handle_starttag(self, tag, attrs):
        if tag == 'pre':
            self.in_pre = True
        if tag == 'script':
            self.in_script = True
        if tag == 'style':
            self.in_style = True
        self.output.write(f'<{tag}')
        for attr, value in attrs:
            if value is None:
                self.output.write(f' {attr}')
            else:
                self.output.write(f' {attr}="{value}"')
        self.output.write('>')
        
    def handle_endtag(self, tag):
        if tag == 'pre':
            self.in_pre = False
        if tag == 'script':
            self.in_script = False
        if tag == 'style':
            self.in_style = False
        self.output.write(f'</{tag}>')
        
    def handle_data(self, data):
        if self.in_pre or self.in_script or self.in_style:
            # Preserve content in pre, script, and style tags
            self.output.write(data)
        else:
            # Remove extra whitespace in regular content
            data = re.sub(r'\s+', ' ', data)
            if data.strip():
                self.output.write(data)
                
    def handle_comment(self, data):
        # Skip HTML comments but preserve code structure
        pass
        
    def get_minified(self):
        return self.output.getvalue()


def load_exclusions():
    """Load exclusion patterns from donotbuild.yaml"""
    try:
        with open('donotbuild.yaml', 'r') as f:
            config = yaml.safe_load(f)
            return config.get('exclude', [])
    except FileNotFoundError:
        print("⚠️  donotbuild.yaml not found, using default exclusions")
        return ['*.yaml', '*.yml', 'build.py', 'README.md', '.git*']


def should_exclude(file_path, exclusions):
    """Check if file matches any exclusion pattern"""
    file_name = os.path.basename(file_path)
    for pattern in exclusions:
        if pattern.startswith('*.'):
            # Extension match - check just the filename
            ext = pattern[1:]
            if file_name.endswith(ext):
                return True
        elif '*' in pattern:
            # Glob pattern like "pixi.*"
            import fnmatch
            if fnmatch.fnmatch(file_name, pattern):
                return True
        elif pattern in file_path:
            # Substring match for directories
            return True
    return False


def minify_html(html_content):
    """Minify HTML content"""
    try:
        minifier = HTMLMinifier()
        minifier.feed(html_content)
        minified = minifier.get_minified()
        return minified
    except Exception as e:
        print(f"⚠️  HTML minification failed: {e}, using original")
        return html_content


def minify_css(css_content):
    """Basic CSS minification"""
    # Remove comments
    css = re.sub(r'/\*.*?\*/', '', css_content, flags=re.DOTALL)
    # Remove whitespace
    css = re.sub(r'\s+', ' ', css)
    css = re.sub(r'\s*([{}:;,])\s*', r'\1', css)
    return css.strip()


def minify_js(js_content):
    """Basic JS minification - just remove multi-line comments and trim whitespace carefully"""
    # Remove multi-line comments
    js = re.sub(r'/\*.*?\*/', '', js_content, flags=re.DOTALL)
    # Remove single-line comments but be very careful
    js = re.sub(r'^\s*//.*?$', '', js, flags=re.MULTILINE)
    # Only normalize excessive whitespace, don't collapse all spaces
    js = re.sub(r'\n\s*\n', '\n', js)
    return js


def parse_event_date(date_str):
    """Parse various date formats and return datetime object or None"""
    if not date_str or date_str.strip().upper() == 'TBA':
        return None

    # Extract date part before any comma (e.g., "15 October 2025, Thursday ...")
    date_part = date_str.split(',')[0].strip()

    # Try ISO format first (YYYY-MM-DD)
    for fmt in ['%Y-%m-%d', '%d %B %Y', '%d %b %Y']:
        try:
            parsed_date = datetime.strptime(date_part, fmt).date()
            # Default time is midnight
            return datetime.combine(parsed_date, time(0, 0))
        except ValueError:
            continue

    return None


def parse_event_datetime_with_tz(date_str):
    """Return an aware UTC datetime parsed from a human date string.

    If the input contains a time, try to parse it (e.g. "(1:20PM)" or "1:20PM").
    If no timezone is present we assume Asia/Kolkata (IST) as requested and
    return a UTC-converted aware datetime. If parsing fails, return None.
    """
    if not date_str or date_str.strip().upper() == 'TBA':
        return None

    # Base date parsing
    base_dt = parse_event_date(date_str)
    if base_dt is None:
        return None

    # Attempt to extract time like 1:20PM or 01:20 PM
    time_match = re.search(r'(\d{1,2}:\d{2}\s*[APMapm]{2})', date_str)
    hour = 0
    minute = 0
    if time_match:
        tstr = time_match.group(1).strip().upper().replace(' ', '')
        try:
            # Normalize to HH:MMAM/PM
            tm = datetime.strptime(tstr, '%I:%M%p')
            hour = tm.hour
            minute = tm.minute
        except Exception:
            pass
    else:
        # Try patterns like "1st Hour" or "2nd Hour" -> treat as hour:00
        hour_match = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s*Hour', date_str, flags=re.IGNORECASE)
        if hour_match:
            try:
                hour = int(hour_match.group(1))
                minute = 0
            except Exception:
                hour = 0
                minute = 0

    # Combine date and time
    combined = datetime.combine(base_dt.date(), time(hour % 24, minute))

    # If ZoneInfo is available, assume Asia/Kolkata when unspecified
    try:
        if ZoneInfo is not None:
            local_tz = ZoneInfo('Asia/Kolkata')
            local_dt = combined.replace(tzinfo=local_tz)
            utc_dt = local_dt.astimezone(ZoneInfo('UTC'))
            return utc_dt
        else:
            # ZoneInfo not available; return naive UTC-like datetime
            return combined
    except Exception:
        # On any failure, return naive datetime (best-effort)
        return combined


def attach_date_utc_to_event(event):
    """Attach a date_utc (ISO 8601 Z) field to the event dict if parsable."""
    date_str = event.get('date') or ''
    dt_utc = parse_event_datetime_with_tz(date_str)
    if dt_utc is None:
        event['date_utc'] = None
    else:
        # Produce RFC3339-like UTC string with Z
        try:
            # If tz-aware, convert to UTC and emit Z
            if dt_utc.tzinfo is not None:
                iso = dt_utc.astimezone(ZoneInfo('UTC')).isoformat()
            else:
                iso = dt_utc.isoformat()
            # Normalize +00:00 to Z
            if iso.endswith('+00:00'):
                iso = iso.replace('+00:00', 'Z')
            event['date_utc'] = iso
        except Exception:
            event['date_utc'] = dt_utc.isoformat()


def generate_rss_feed(events, title, description, link, output_file):
    """Generate RSS 2.0 feed for events"""
    rss_items = []
    
    for event in events:
        event_title = escape(event.get('title', 'Untitled Event'))
        event_desc = escape(event.get('description', ''))
        event_location = escape(event.get('location', 'TBD'))
        event_duration = escape(event.get('duration', ''))
        event_date_str = event.get('date', 'TBD')

        # Prefer using date_utc if present for pubDate
        event_date_utc = event.get('date_utc')
        pub_date = None
        if event_date_utc:
            try:
                # parse ISO format, fallback to now
                pub_dt = datetime.fromisoformat(event_date_utc.replace('Z', '+00:00'))
                pub_date = pub_dt.strftime('%a, %d %b %Y %H:%M:%S +0000')
            except Exception:
                pub_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
        else:
            pub_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
        
        # Build full description with all details
        full_description = f"{event_desc}"
        if event_location:
            full_description += f"<br/><br/><strong>Location:</strong> {event_location}"
        if event_duration:
            full_description += f"<br/><strong>Duration:</strong> {event_duration}"
        if event_date_str:
            full_description += f"<br/><strong>Date:</strong> {escape(event_date_str)}"
        
        # Add optional links
        if event.get('signup_url'):
            signup_url = escape(event['signup_url'])
            full_description += f'<br/><br/><a href="{signup_url}">Sign Up Here</a>'
        if event.get('instructions_url'):
            instructions_url = escape(event['instructions_url'])
            full_description += f'<br/><a href="{instructions_url}">View Instructions</a>'
        # Create unique GUID (using title + date_utc or date as unique identifier)
        guid_id = event.get('date_utc') or event_date_str
        guid = f"{link}/#{event_title.replace(' ', '-').lower()}-{guid_id}"

        rss_item = f"""    <item>
      <title>{event_title}</title>
      <description><![CDATA[{full_description}]]></description>
      <pubDate>{pub_date}</pubDate>
      <link>{link}</link>
      <guid isPermaLink="false">{guid}</guid>
    </item>"""
        rss_items.append(rss_item)
    
    # Build complete RSS feed
    last_build_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
    
    rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(title)}</title>
    <description>{escape(description)}</description>
    <link>{link}</link>
    <atom:link href="{link}/events/index.xml" rel="self" type="application/rss+xml" />
    <language>en-us</language>
    <lastBuildDate>{last_build_date}</lastBuildDate>
{chr(10).join(rss_items)}
  </channel>
</rss>
"""
    
    # Write RSS feed
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(rss_content)
    
    print(f"✓ Generated RSS: {output_file}")
    return output_file

def convert_yaml_to_json(yaml_file, output_dir):
    """Convert YAML file to JSON and sort events by date"""
    try:
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)
        
        # If this is events.yaml, categorize and sort events by date
        if 'current_events' in data or 'past_events' in data:
            current_events = data.get('current_events', []) or []
            past_events = data.get('past_events', []) or []

            # Combine and re-categorize based on date
            all_events = current_events + past_events
            new_current = []
            new_past = []

            # Attach UTC dates to all events
            for event in all_events:
                attach_date_utc_to_event(event)

            # Determine now in UTC
            if ZoneInfo is not None:
                now_utc = datetime.now(ZoneInfo('UTC'))
            else:
                now_utc = datetime.utcnow()

            for event in all_events:
                date_utc = event.get('date_utc')
                if date_utc:
                    try:
                        ev_dt = datetime.fromisoformat(date_utc.replace('Z', '+00:00'))
                        # Compare in UTC
                        if ev_dt < now_utc:
                            new_past.append(event)
                        else:
                            new_current.append(event)
                    except Exception:
                        # If parsing fails, treat as current
                        new_current.append(event)
                else:
                    # No date -> consider current
                    new_current.append(event)

            # Sorting: current ascending (earliest first), past descending (newest first)
            def sort_key_asc(event):
                d = event.get('date_utc')
                if not d:
                    return datetime.max
                try:
                    return datetime.fromisoformat(d.replace('Z', '+00:00'))
                except Exception:
                    return datetime.max

            def sort_key_desc(event):
                d = event.get('date_utc')
                if not d:
                    return datetime.min
                try:
                    return datetime.fromisoformat(d.replace('Z', '+00:00'))
                except Exception:
                    return datetime.min

            new_current.sort(key=sort_key_asc)
            new_past.sort(key=sort_key_desc, reverse=True)

            data['current_events'] = new_current
            data['past_events'] = new_past
            
            # Generate RSS feeds for events
            base_url = "https://neotechclub.qzz.io"
            
            # Always generate events/index.xml (main feed) - use current events if available, otherwise empty
            events_rss = os.path.join(output_dir, 'events', 'index.xml')
            generate_rss_feed(
                new_current,
                "NeoTech Club - Current Events",
                "Upcoming events and activities at NeoTech Club @ GCC",
                base_url,
                events_rss
            )
            
            # Copy to events/current/index.xml as well
            current_rss = os.path.join(output_dir, 'events', 'current', 'index.xml')
            os.makedirs(os.path.dirname(current_rss), exist_ok=True)
            shutil.copy2(events_rss, current_rss)
            print(f"✓ Copied RSS: {current_rss}")
            
            # Past events RSS at events/past/index.xml
            past_rss = os.path.join(output_dir, 'events', 'past', 'index.xml')
            generate_rss_feed(
                new_past,
                "NeoTech Club - Past Events",
                "Archive of past events and activities at NeoTech Club @ GCC",
                base_url,
                past_rss
            )
        
        # Write JSON output
        output_file = os.path.join(output_dir, os.path.splitext(os.path.basename(yaml_file))[0] + '.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"✓ Converted: {yaml_file} → {output_file}")
    except Exception as e:
        print(f"✗ Failed to convert {yaml_file}: {e}")


def process_file(file_path, output_dir, exclusions):
    """Process a single file - minify if applicable, copy to output"""
    if should_exclude(file_path, exclusions):
        return False
    
    # Create output path
    rel_path = os.path.relpath(file_path)
    output_path = os.path.join(output_dir, rel_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    try:
        # Handle different file types
        if file_path.endswith('.html'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            minified = minify_html(content)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(minified)
            print(f"✓ Minified HTML: {file_path}")
            
        elif file_path.endswith('.css'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            minified = minify_css(content)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(minified)
            print(f"✓ Minified CSS: {file_path}")
            
        elif file_path.endswith('.js') and not 'node_modules' in file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            minified = minify_js(content)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(minified)
            print(f"✓ Minified JS: {file_path}")
            
        else:
            # Copy other files as-is
            shutil.copy2(file_path, output_path)
            print(f"✓ Copied: {file_path}")
        
        return True
    except Exception as e:
        print(f"✗ Failed to process {file_path}: {e}")
        return False


def build_site():
    """Main build function"""
    print("=" * 60)
    print("🔨 NeoTech Club Website Build")
    print("=" * 60)
    
    # Setup
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)  # Ensure we're in the script directory
    
    output_dir = 'out'
    exclusions = load_exclusions()
    
    print(f"\n📋 Exclusions: {', '.join(exclusions)}\n")
    
    # Clean and create output directory
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    
    # Convert YAML files to JSON
    print("\n📄 Converting YAML to JSON...")
    yaml_files = ['schedule.yaml', 'events.yaml', 'team.yaml']
    
    for yaml_file in yaml_files:
        if os.path.exists(yaml_file):
            convert_yaml_to_json(yaml_file, output_dir)
    
    # Process all other files
    print("\n📦 Processing files...")
    processed = 0
    for root, dirs, files in os.walk('.'):
        # Skip hidden directories and output dir
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'out']
        
        for file in files:
            file_path = os.path.join(root, file)
            if process_file(file_path, output_dir, exclusions):
                processed += 1
    
    print("\n" + "=" * 60)
    print(f"✅ Build complete! Processed {processed} files")
    print(f"📁 Output directory: {os.path.abspath(output_dir)}")
    print("=" * 60)


if __name__ == '__main__':
    try:
        build_site()
    except KeyboardInterrupt:
        print("\n\n⚠️  Build cancelled by user")
    except Exception as e:
        print(f"\n\n✗ Build failed: {e}")
        raise
