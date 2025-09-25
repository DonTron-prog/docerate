#!/usr/bin/env python3
import os
import sys
import yaml
import json
import shutil
import argparse
import http.server
import socketserver
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.tables import TableExtension
from markdown.extensions.toc import TocExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.footnotes import FootnoteExtension
from markdown.extensions.attr_list import AttrListExtension
from pymdownx import superfences, tasklist
from jinja2 import Environment, FileSystemLoader
from pygments.formatters import HtmlFormatter
from PIL import Image
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class BlogPost:
    def __init__(self, filepath: Path, config: dict):
        self.filepath = filepath
        self.config = config
        self.content = ""
        self.metadata = {}
        self.html = ""
        self.url = ""
        self._parse()
    
    def _parse(self):
        with open(self.filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse frontmatter
        if content.startswith('---'):
            _, frontmatter, content = content.split('---', 2)
            self.metadata = yaml.safe_load(frontmatter)
            self.content = content.strip()
        else:
            self.content = content
            self.metadata = {}
        
        # Set defaults
        self.metadata.setdefault('title', self.filepath.stem.replace('-', ' ').title())
        self.metadata.setdefault('date', datetime.fromtimestamp(self.filepath.stat().st_mtime))
        self.metadata.setdefault('tags', [])
        self.metadata.setdefault('category', 'uncategorized')
        
        # Normalize date to datetime object
        if isinstance(self.metadata['date'], str):
            # Parse string dates
            try:
                self.metadata['date'] = datetime.strptime(self.metadata['date'], '%Y-%m-%d')
            except ValueError:
                try:
                    self.metadata['date'] = datetime.strptime(self.metadata['date'], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    # Use file modification time as fallback
                    self.metadata['date'] = datetime.fromtimestamp(self.filepath.stat().st_mtime)
        elif hasattr(self.metadata['date'], 'date'):
            # Convert date to datetime
            if not isinstance(self.metadata['date'], datetime):
                self.metadata['date'] = datetime.combine(self.metadata['date'], datetime.min.time())
        
        # Generate URL
        date = self.metadata['date']
        self.url = f"/{date.year}/{date.month:02d}/{self.filepath.stem}.html"
        
        # Convert markdown to HTML
        md = markdown.Markdown(extensions=[
            'markdown.extensions.meta',
            CodeHiliteExtension(css_class='highlight', linenums=False),
            TableExtension(),
            TocExtension(permalink=True),
            FencedCodeExtension(),
            FootnoteExtension(),
            AttrListExtension(),
            'pymdownx.superfences',
            'pymdownx.tasklist',
        ])
        self.html = md.convert(self.content)
        
        # Fix image paths to point to /images/ directory
        import re
        self.html = re.sub(
            r'<img([^>]*?)src="([^"]*?\.(?:jpg|jpeg|png|gif|webp))"([^>]*?)>',
            r'<img\1src="/images/\2"\3>',
            self.html,
            flags=re.IGNORECASE
        )
        
        # Extract excerpt
        excerpt_length = self.config['blog']['excerpt_length']
        text_only = ' '.join(self.html.split()[:excerpt_length])
        self.metadata['excerpt'] = text_only.split('</p>')[0] + '</p>'
        
        # Extract first image from markdown content
        self.extract_first_image()
    
    def extract_first_image(self):
        """Extract the first image from frontmatter or markdown content"""
        import re
        
        # First check if image is specified in frontmatter
        if 'image' in self.metadata and self.metadata['image']:
            image_filename = self.metadata['image']
            # Clean up the image filename (remove any path)
            image_filename = image_filename.split('/')[-1]
            # Generate thumbnail filename
            name, ext = image_filename.rsplit('.', 1)
            self.metadata['first_image'] = image_filename
            self.metadata['first_image_thumb'] = f"{name}_thumb.{ext}"
            return
        
        # If not in frontmatter, look for markdown image syntax: ![alt](image.jpg)
        image_pattern = r'!\[.*?\]\(([^)]+\.(?:jpg|jpeg|png|gif|webp))\)'
        match = re.search(image_pattern, self.content, re.IGNORECASE)
        
        if match:
            image_filename = match.group(1)
            # Clean up the image filename (remove any path)
            image_filename = image_filename.split('/')[-1]
            # Generate thumbnail filename
            name, ext = image_filename.rsplit('.', 1)
            self.metadata['first_image'] = image_filename
            self.metadata['first_image_thumb'] = f"{name}_thumb.{ext}"
        else:
            self.metadata['first_image'] = None
            self.metadata['first_image_thumb'] = None


class StaticSiteGenerator:
    def __init__(self, config_file='config.yaml'):
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.content_dir = Path(self.config['build']['content_dir'])
        self.output_dir = Path(self.config['build']['output_dir'])
        self.static_dir = Path(self.config['build']['static_dir'])
        self.templates_dir = Path(self.config['build']['templates_dir'])
        
        self.env = Environment(loader=FileSystemLoader(self.templates_dir))
        self.env.globals['current_year'] = datetime.now().year
        self.posts = []
        self.tags = {}
        self.categories = {}
    
    def clean(self):
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def load_posts(self):
        self.posts = []
        posts_dir = self.content_dir / 'posts'
        
        if not posts_dir.exists():
            return
        
        for filepath in posts_dir.glob('*.md'):
            post = BlogPost(filepath, self.config)
            self.posts.append(post)
            
            # Organize by tags
            for tag in post.metadata.get('tags', []):
                if tag not in self.tags:
                    self.tags[tag] = []
                self.tags[tag].append(post)
            
            # Organize by category
            category = post.metadata.get('category', 'uncategorized')
            if category not in self.categories:
                self.categories[category] = []
            self.categories[category].append(post)
        
        # Sort posts by date (newest first)
        self.posts.sort(key=lambda p: p.metadata['date'], reverse=True)
    
    def copy_static(self):
        if self.static_dir.exists():
            shutil.copytree(self.static_dir, self.output_dir / 'static', dirs_exist_ok=True)

            # Copy robots.txt and llms.txt to root
            robots_src = self.static_dir / 'robots.txt'
            llms_src = self.static_dir / 'llms.txt'

            if robots_src.exists():
                shutil.copy2(robots_src, self.output_dir / 'robots.txt')

            if llms_src.exists():
                shutil.copy2(llms_src, self.output_dir / 'llms.txt')
    
    def copy_images(self):
        images_dir = self.content_dir / 'images'
        if images_dir.exists():
            output_images = self.output_dir / 'images'
            output_images.mkdir(exist_ok=True)
            
            for img_path in images_dir.glob('*'):
                if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    shutil.copy2(img_path, output_images)
                    
                    # Create thumbnail if it's a large image
                    if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                        self._create_thumbnail(img_path, output_images)
    
    def _create_thumbnail(self, img_path, output_dir):
        try:
            img = Image.open(img_path)
            img.thumbnail((400, 400))
            thumb_path = output_dir / f"{img_path.stem}_thumb{img_path.suffix}"
            img.save(thumb_path, optimize=True)
        except Exception as e:
            print(f"Failed to create thumbnail for {img_path}: {e}")
    
    def generate_post(self, post):
        # Create output directory
        output_path = self.output_dir / post.url.strip('/')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Render template
        template = self.env.get_template('post.html')
        html = template.render(
            post=post,
            site=self.config['site'],
            config=self.config,
            recent_posts=self.posts[:5]
        )
        
        # Write file
        output_path.write_text(html, encoding='utf-8')
    
    def generate_index(self):
        template = self.env.get_template('index.html')
        html = template.render(
            posts=self.posts,
            site=self.config['site'],
            config=self.config,
            tags=self.tags,
            categories=self.categories
        )
        
        (self.output_dir / 'index.html').write_text(html, encoding='utf-8')
    
    def generate_tag_pages(self):
        template = self.env.get_template('tag.html')
        tags_dir = self.output_dir / 'tags'
        tags_dir.mkdir(exist_ok=True)
        
        for tag, posts in self.tags.items():
            html = template.render(
                tag=tag,
                posts=posts,
                site=self.config['site'],
                config=self.config
            )
            (tags_dir / f'{tag}.html').write_text(html, encoding='utf-8')
        
        # Generate tags index page
        tags_index_template = self.env.get_template('tags_index.html')
        tags_index_html = tags_index_template.render(
            tags=self.tags,
            site=self.config['site'],
            config=self.config
        )
        (tags_dir / 'index.html').write_text(tags_index_html, encoding='utf-8')
    
    def generate_archive_page(self):
        template = self.env.get_template('archive.html')
        html = template.render(
            posts=self.posts,
            site=self.config['site'],
            config=self.config
        )
        archive_dir = self.output_dir / 'archive'
        archive_dir.mkdir(exist_ok=True)
        (archive_dir / 'index.html').write_text(html, encoding='utf-8')
    
    def generate_404_page(self):
        template = self.env.get_template('404.html')
        html = template.render(
            site=self.config['site'],
            config=self.config
        )
        (self.output_dir / '404.html').write_text(html, encoding='utf-8')
    
    def generate_search_index(self):
        if not self.config['features']['search']:
            return

        search_data = []
        for post in self.posts:
            search_data.append({
                'title': post.metadata['title'],
                'url': post.url,
                'content': ' '.join(post.content.split()[:200]),
                'tags': post.metadata.get('tags', []),
                'date': post.metadata['date'].isoformat()
            })

        (self.output_dir / 'search.json').write_text(
            json.dumps(search_data), encoding='utf-8'
        )

    def generate_sitemap(self):
        """Generate XML sitemap for search engines and AI crawlers"""
        urlset = ET.Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')

        # Add homepage
        url = ET.SubElement(urlset, 'url')
        ET.SubElement(url, 'loc').text = self.config['site']['url'] + '/'
        ET.SubElement(url, 'changefreq').text = 'weekly'
        ET.SubElement(url, 'priority').text = '1.0'

        # Add static pages
        static_pages = ['/about/', '/archive/', '/tags/']
        for page in static_pages:
            url = ET.SubElement(urlset, 'url')
            ET.SubElement(url, 'loc').text = self.config['site']['url'] + page
            ET.SubElement(url, 'changefreq').text = 'monthly'
            ET.SubElement(url, 'priority').text = '0.8'

        # Add blog posts
        for post in self.posts:
            url = ET.SubElement(urlset, 'url')
            ET.SubElement(url, 'loc').text = self.config['site']['url'] + post.url
            ET.SubElement(url, 'lastmod').text = post.metadata['date'].strftime('%Y-%m-%d')
            ET.SubElement(url, 'changefreq').text = 'monthly'
            ET.SubElement(url, 'priority').text = '0.7'

        # Add tag pages
        for tag in self.tags:
            url = ET.SubElement(urlset, 'url')
            ET.SubElement(url, 'loc').text = f"{self.config['site']['url']}/tags/{tag}.html"
            ET.SubElement(url, 'changefreq').text = 'weekly'
            ET.SubElement(url, 'priority').text = '0.5'

        # Write sitemap
        tree = ET.ElementTree(urlset)
        ET.indent(tree, space='  ')
        sitemap_path = self.output_dir / 'sitemap.xml'
        tree.write(sitemap_path, encoding='utf-8', xml_declaration=True)
        print(f"  Generated sitemap.xml with {len(self.posts)} posts")

    def generate_llms_txt(self):
        """Generate dynamic llms.txt file for AI agents"""
        content = []
        content.append("# " + self.config['site']['title'])
        content.append("")
        content.append("> " + self.config['site']['description'])
        content.append("")
        content.append("## About This Site")
        content.append("")
        content.append(f"This blog explores the intersection of artificial intelligence, software engineering, and system reliability. Content focuses on practical implementations, research insights, and technical deep-dives into emerging technologies.")
        content.append("")
        content.append(f"**Author**: {self.config['site']['author']}")
        content.append(f"**URL**: {self.config['site']['url']}")
        content.append(f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}")
        content.append(f"**Total Posts**: {len(self.posts)}")
        content.append("")
        content.append("## Recent Content")
        content.append("")

        # Add recent posts
        for post in self.posts[:10]:
            content.append(f"### {post.metadata['title']}")
            content.append(f"*Published: {post.metadata['date'].strftime('%Y-%m-%d')}*")
            if post.metadata.get('description'):
                content.append(post.metadata['description'])
            content.append(f"URL: {self.config['site']['url']}{post.url}")
            if post.metadata.get('tags'):
                content.append(f"Tags: {', '.join(post.metadata['tags'])}")
            content.append("")

        content.append("## Content Categories")
        content.append("")

        # Group posts by category
        categories_dict = {}
        for post in self.posts:
            cat = post.metadata.get('category', 'uncategorized')
            if cat not in categories_dict:
                categories_dict[cat] = []
            categories_dict[cat].append(post.metadata['title'])

        for category, titles in categories_dict.items():
            content.append(f"### {category.title()}")
            for title in titles[:5]:  # Limit to 5 posts per category
                content.append(f"- {title}")
            if len(titles) > 5:
                content.append(f"- ...and {len(titles) - 5} more")
            content.append("")

        content.append("## API and Feeds")
        content.append("")
        content.append("- **RSS Feed**: `/rss.xml`")
        content.append("- **Sitemap**: `/sitemap.xml`")
        content.append("- **Search Index**: `/search.json`")
        content.append("- **robots.txt**: `/robots.txt`")
        content.append("")
        content.append("## Technical Implementation")
        content.append("")
        content.append("- **Static Site Generator**: Custom Python-based SSG with Markdown support")
        content.append("- **Hosting**: AWS S3 + CloudFront CDN")
        content.append("- **Search**: Client-side JSON index with full-text search")
        content.append("- **Schema Markup**: JSON-LD structured data for all content")
        content.append("- **AI Optimization**: Schema.org markup, semantic HTML, OpenGraph tags")
        content.append("")
        content.append("## Usage Guidelines")
        content.append("")
        content.append("When referencing content from this site:")
        content.append("1. Articles contain technical implementations with code examples")
        content.append("2. Focus on practical applications and real-world use cases")
        content.append("3. Content includes both theoretical background and hands-on tutorials")
        content.append("4. Code snippets are production-ready and tested")
        content.append("5. Please provide attribution when citing or adapting content")
        content.append("")
        content.append("---")
        content.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        # Write llms.txt
        llms_path = self.output_dir / 'llms.txt'
        llms_path.write_text('\n'.join(content), encoding='utf-8')
        print(f"  Generated llms.txt with {len(self.posts)} posts indexed")

    def generate_rss(self):
        """Generate RSS feed with structured data"""
        rss = ET.Element('rss', version='2.0',
                        attrib={'xmlns:content': 'http://purl.org/rss/1.0/modules/content/',
                               'xmlns:atom': 'http://www.w3.org/2005/Atom'})
        channel = ET.SubElement(rss, 'channel')

        # Channel metadata
        ET.SubElement(channel, 'title').text = self.config['site']['title']
        ET.SubElement(channel, 'link').text = self.config['site']['url']
        ET.SubElement(channel, 'description').text = self.config['site']['description']
        ET.SubElement(channel, 'language').text = self.config['site']['language']
        ET.SubElement(channel, 'lastBuildDate').text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')

        # Atom link
        atom_link = ET.SubElement(channel, '{http://www.w3.org/2005/Atom}link')
        atom_link.set('href', f"{self.config['site']['url']}/rss.xml")
        atom_link.set('rel', 'self')
        atom_link.set('type', 'application/rss+xml')

        # Add posts (limit to 20 most recent)
        for post in self.posts[:20]:
            item = ET.SubElement(channel, 'item')
            ET.SubElement(item, 'title').text = post.metadata['title']
            ET.SubElement(item, 'link').text = self.config['site']['url'] + post.url
            ET.SubElement(item, 'guid', isPermaLink='true').text = self.config['site']['url'] + post.url

            # Add description
            description = post.metadata.get('description', '')
            if not description:
                # Generate excerpt from content
                description = ' '.join(post.content.split()[:30]) + '...'
            ET.SubElement(item, 'description').text = description

            # Add full content
            content_encoded = ET.SubElement(item, '{http://purl.org/rss/1.0/modules/content/}encoded')
            content_encoded.text = post.html

            # Add metadata
            ET.SubElement(item, 'pubDate').text = post.metadata['date'].strftime('%a, %d %b %Y %H:%M:%S %z')
            ET.SubElement(item, 'author').text = self.config['site']['author']

            # Add categories/tags
            for tag in post.metadata.get('tags', []):
                ET.SubElement(item, 'category').text = tag

        # Write RSS feed
        tree = ET.ElementTree(rss)
        ET.indent(tree, space='  ')
        rss_path = self.output_dir / 'rss.xml'
        tree.write(rss_path, encoding='utf-8', xml_declaration=True)
        print(f"  Generated rss.xml with {min(20, len(self.posts))} posts")
    
    def generate_about_page(self):
        template = self.env.get_template('about.html')
        html = template.render(
            site=self.config['site'],
            config=self.config
        )
        about_dir = self.output_dir / 'about'
        about_dir.mkdir(exist_ok=True)
        (about_dir / 'index.html').write_text(html, encoding='utf-8')
    
    def generate_css(self):
        # Generate Pygments CSS for syntax highlighting
        if self.config['features']['syntax_highlighting']:
            formatter = HtmlFormatter(style='monokai')
            css = formatter.get_style_defs('.highlight')
            
            css_dir = self.output_dir / 'static'
            css_dir.mkdir(exist_ok=True)
            (css_dir / 'pygments.css').write_text(css)
    
    def build(self):
        print("Building site...")
        self.clean()
        self.load_posts()
        self.copy_static()
        self.copy_images()
        self.generate_css()
        
        # Generate pages
        for post in self.posts:
            self.generate_post(post)
            print(f"  Generated: {post.url}")
        
        self.generate_index()
        self.generate_tag_pages()
        self.generate_archive_page()
        self.generate_about_page()
        self.generate_404_page()
        self.generate_search_index()
        self.generate_sitemap()
        self.generate_rss()
        self.generate_llms_txt()

        print(f"\nBuild complete! {len(self.posts)} posts generated.")
    
    def serve(self, port=8000):
        os.chdir(self.output_dir)
        
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory='.', **kwargs)
            
            def do_GET(self):
                # Try to serve the file normally
                if os.path.exists(self.translate_path(self.path)):
                    super().do_GET()
                else:
                    # Serve custom 404 page
                    self.send_error(404)
            
            def send_error(self, code, message=None):
                if code == 404 and os.path.exists('404.html'):
                    self.send_response(404)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    with open('404.html', 'rb') as f:
                        self.wfile.write(f.read())
                else:
                    super().send_error(code, message)
        
        with socketserver.TCPServer(("", port), Handler) as httpd:
            print(f"Serving at http://localhost:{port}")
            print("Press Ctrl+C to stop")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nServer stopped.")
    
    def watch(self):
        class BuildHandler(FileSystemEventHandler):
            def __init__(self, generator):
                self.generator = generator
            
            def on_modified(self, event):
                if not event.is_directory:
                    print(f"Detected change in {event.src_path}")
                    self.generator.build()
        
        event_handler = BuildHandler(self)
        observer = Observer()
        observer.schedule(event_handler, str(self.content_dir), recursive=True)
        observer.schedule(event_handler, str(self.templates_dir), recursive=True)
        observer.start()
        
        print("Watching for changes...")
        try:
            while True:
                pass
        except KeyboardInterrupt:
            observer.stop()
        observer.join()


def main():
    parser = argparse.ArgumentParser(description='Static Site Generator')
    parser.add_argument('command', choices=['build', 'serve', 'watch', 'new'])
    parser.add_argument('--port', type=int, default=8000, help='Port for serve command')
    parser.add_argument('--title', help='Title for new post')
    
    args = parser.parse_args()
    generator = StaticSiteGenerator()
    
    if args.command == 'build':
        generator.build()
    elif args.command == 'serve':
        generator.build()
        generator.serve(args.port)
    elif args.command == 'watch':
        generator.build()
        generator.watch()
    elif args.command == 'new':
        # Create new post template
        title = args.title or input("Post title: ")
        slug = title.lower().replace(' ', '-')
        date = datetime.now()
        
        post_path = Path(f"content/posts/{slug}.md")
        post_path.parent.mkdir(parents=True, exist_ok=True)
        
        template = f"""---
title: "{title}"
date: {date.strftime('%Y-%m-%d')}
tags: []
category: general
description: ""
image: ""
---

# {title}

Write your content here...
"""
        post_path.write_text(template)
        print(f"Created new post: {post_path}")


if __name__ == '__main__':
    main()