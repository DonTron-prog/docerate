#!/usr/bin/env python3
import os
import sys
import yaml
import json
import shutil
import argparse
import http.server
import socketserver
from datetime import datetime
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
        
        # Extract excerpt
        excerpt_length = self.config['blog']['excerpt_length']
        text_only = ' '.join(self.html.split()[:excerpt_length])
        self.metadata['excerpt'] = text_only.split('</p>')[0] + '</p>'


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
        self.generate_search_index()
        
        print(f"\nBuild complete! {len(self.posts)} posts generated.")
    
    def serve(self, port=8000):
        os.chdir(self.output_dir)
        
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory='.', **kwargs)
        
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
---

# {title}

Write your content here...
"""
        post_path.write_text(template)
        print(f"Created new post: {post_path}")


if __name__ == '__main__':
    main()