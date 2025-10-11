#!/usr/bin/env python3
"""
NeoTech Club Website Build Script
Converts YAML to JSON, minifies HTML/CSS/JS, and outputs to out/ folder.
Respects exclusions listed in donotbuild.yaml
"""

import os
import re
import io
import json
import yaml
import shutil
import fnmatch
from datetime import datetime
from pathlib import Path
from html.parser import HTMLParser


class HTMLMinifier(HTMLParser):
    """Simple HTML minifier that removes unnecessary whitespace but preserves script/style content"""
    def __init__(self):
        super().__init__()
        self.output = io.StringIO()
        self.in_pre = False
        self.in_script = False
        self.in_style = False
        
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
    if not date_str or date_str.upper() == 'TBA':
        return None
    
    # Try ISO format first (YYYY-MM-DD)
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        pass
    
    # Try formats like "10 October 2025" or "10 Oct 2025"
    for fmt in ['%d %B %Y', '%d %b %Y']:
        try:
            # Extract just the date part before comma if present
            date_part = date_str.split(',')[0].strip()
            return datetime.strptime(date_part, fmt)
        except ValueError:
            continue
    
    return None

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
            today = datetime.now().date()
            
            for event in all_events:
                event_date = parse_event_date(event.get('date', ''))
                if event_date and event_date.date() < today:
                    new_past.append(event)
                else:
                    # Keep as current if no date, TBA, or future date
                    new_current.append(event)
            
            # Sort past events by date (newest first)
            def get_event_date(event):
                date_obj = parse_event_date(event.get('date', ''))
                return date_obj if date_obj else datetime.min
            
            new_past.sort(key=get_event_date, reverse=True)
            
            data['current_events'] = new_current
            data['past_events'] = new_past
        
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
    yaml_files = ['schedule.yaml', 'events.yaml']
    
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
