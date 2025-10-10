#!/usr/bin/env python3
"""
Generate static JSON files from markdown blog posts for frontend consumption.
This allows blog posts to be served as static files from CloudFront instead of through Lambda.
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import frontmatter
import markdown

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


class StaticPostGenerator:
    """Generate static JSON files from markdown posts."""

    def __init__(self):
        self.content_dir = Path("content/posts")
        self.output_dir = Path("rag-frontend/public/static-data")
        self.posts_dir = self.output_dir / "posts"

        # Markdown processor with extensions
        self.md = markdown.Markdown(
            extensions=[
                'meta',
                'codehilite',
                'fenced_code',
                'tables',
                'toc',
                'footnotes',
                'attr_list',
                'def_list',
                'abbr',
                'md_in_html',
                'admonition',
                'nl2br',
                'sane_lists',
                'smarty',
                'wikilinks'
            ],
            extension_configs={
                'codehilite': {
                    'css_class': 'highlight',
                    'pygments_style': 'monokai',
                    'linenums': False
                }
            }
        )

    def _parse_filename(self, filename: str) -> Dict[str, Any]:
        """Extract metadata from post filename."""
        name = filename.replace('.md', '')
        parts = name.split('-', 3)

        # Try to parse as YYYY-MM-DD-slug format
        if len(parts) >= 4:
            try:
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                date = datetime(year, month, day)
                slug = parts[3]
            except (ValueError, IndexError):
                # Not in date format, use filename as slug
                date = datetime.now()
                slug = name.lower().replace(' ', '-').replace('_', '-')
        else:
            # Use filename as slug
            date = datetime.now()
            slug = name.lower().replace(' ', '-').replace('_', '-')

        return {
            'date': date.isoformat(),
            'slug': slug
        }

    def _calculate_reading_time(self, content: str) -> int:
        """Calculate estimated reading time in minutes."""
        words = len(content.split())
        # Average reading speed is 200-250 words per minute
        return max(1, round(words / 225))

    def _extract_excerpt(self, content: str, max_length: int = 160) -> str:
        """Extract a clean excerpt from markdown content."""
        # Remove markdown syntax for cleaner excerpt
        text = content
        # Remove code blocks
        import re
        text = re.sub(r'```[^`]*```', '', text)
        text = re.sub(r'`[^`]+`', '', text)
        # Remove links but keep text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # Remove images
        text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', text)
        # Remove headers
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        # Remove emphasis
        text = re.sub(r'[*_]{1,2}([^*_]+)[*_]{1,2}', r'\1', text)
        # Clean up whitespace
        text = ' '.join(text.split())

        if len(text) <= max_length:
            return text

        # Find the last complete word within the limit
        truncated = text[:max_length].rsplit(' ', 1)[0]
        return truncated + '...'

    def generate_post_json(self, file_path: Path) -> Dict[str, Any]:
        """Generate JSON data for a single post."""
        # Parse the post with frontmatter
        with open(file_path, 'r', encoding='utf-8') as f:
            post = frontmatter.load(f)

        # Get metadata from filename
        file_info = self._parse_filename(file_path.name)
        slug = file_info['slug']

        # Extract metadata from frontmatter
        metadata = post.metadata or {}

        # Generate HTML content
        html_content = self.md.convert(post.content)

        # Get and serialize date
        date_value = metadata.get('date', file_info['date'])
        if hasattr(date_value, 'isoformat'):
            # It's a datetime/date object
            date_str = date_value.isoformat()
        elif hasattr(date_value, 'strftime'):
            # It's a date object without isoformat
            date_str = date_value.strftime('%Y-%m-%d')
        elif isinstance(date_value, str):
            # It's already a string
            date_str = date_value
        else:
            # Use current date as fallback
            date_str = datetime.now().isoformat()

        # Build post data
        post_data = {
            'slug': slug,
            'title': metadata.get('title', slug.replace('-', ' ').title()),
            'date': date_str,
            'tags': metadata.get('tags', []),
            'category': metadata.get('category', 'Uncategorized'),
            'description': metadata.get('description', ''),
            'image': metadata.get('image'),
            'content': post.content,
            'html_content': html_content,
            'reading_time': self._calculate_reading_time(post.content),
            'excerpt': self._extract_excerpt(post.content),
            'metadata': {k: v for k, v in metadata.items() if k not in [
                'title', 'date', 'tags', 'category', 'description', 'image'
            ]}
        }

        return post_data

    def generate_posts_index(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate index file with all posts metadata."""
        # Sort posts by date (newest first)
        sorted_posts = sorted(posts, key=lambda x: x['date'], reverse=True)

        # Create summaries (without full content)
        summaries = []
        for post in sorted_posts:
            summary = {
                'slug': post['slug'],
                'title': post['title'],
                'date': post['date'],
                'tags': post['tags'],
                'category': post['category'],
                'description': post['description'],
                'image': post.get('image'),
                'excerpt': post['excerpt'],
                'reading_time': post['reading_time']
            }
            summaries.append(summary)

        return {
            'posts': summaries,
            'total': len(summaries),
            'generated_at': datetime.now().isoformat()
        }

    def generate_tags_index(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate tags index with counts."""
        tags_count = {}
        tags_posts = {}

        for post in posts:
            for tag in post.get('tags', []):
                tags_count[tag] = tags_count.get(tag, 0) + 1
                if tag not in tags_posts:
                    tags_posts[tag] = []
                tags_posts[tag].append(post['slug'])

        # Create tag info list
        tags_info = [
            {
                'name': tag,
                'count': count,
                'posts': tags_posts[tag]
            }
            for tag, count in sorted(tags_count.items())
        ]

        return {
            'tags': tags_info,
            'total': len(tags_info),
            'generated_at': datetime.now().isoformat()
        }

    def run(self):
        """Generate all static files."""
        print("=" * 60)
        print("Static Post Generation")
        print("=" * 60)

        # Create output directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.posts_dir.mkdir(parents=True, exist_ok=True)

        # Check if content directory exists
        if not self.content_dir.exists():
            print(f"Error: Content directory not found: {self.content_dir}")
            return

        # Process all markdown files
        all_posts = []
        post_files = list(self.content_dir.glob("*.md"))

        if not post_files:
            print(f"No markdown files found in {self.content_dir}")
            return

        print(f"Found {len(post_files)} posts to process")

        for file_path in post_files:
            print(f"Processing: {file_path.name}")
            try:
                # Generate post data
                post_data = self.generate_post_json(file_path)
                all_posts.append(post_data)

                # Save individual post JSON
                post_json_path = self.posts_dir / f"{post_data['slug']}.json"
                with open(post_json_path, 'w', encoding='utf-8') as f:
                    json.dump(post_data, f, indent=2, ensure_ascii=False)

                print(f"  ✓ Generated: {post_json_path}")

            except Exception as e:
                print(f"  ✗ Error processing {file_path.name}: {e}")
                continue

        # Generate index files
        print("\nGenerating index files...")

        # Posts index
        posts_index = self.generate_posts_index(all_posts)
        posts_index_path = self.output_dir / "posts-index.json"
        with open(posts_index_path, 'w', encoding='utf-8') as f:
            json.dump(posts_index, f, indent=2, ensure_ascii=False)
        print(f"  ✓ Generated: {posts_index_path}")

        # Tags index
        tags_index = self.generate_tags_index(all_posts)
        tags_index_path = self.output_dir / "tags-index.json"
        with open(tags_index_path, 'w', encoding='utf-8') as f:
            json.dump(tags_index, f, indent=2, ensure_ascii=False)
        print(f"  ✓ Generated: {tags_index_path}")

        # Generate posts by tag files
        tags_posts = {}
        for post in all_posts:
            for tag in post.get('tags', []):
                if tag not in tags_posts:
                    tags_posts[tag] = []
                # Add post summary (not full content)
                tags_posts[tag].append({
                    'slug': post['slug'],
                    'title': post['title'],
                    'date': post['date'],
                    'tags': post['tags'],
                    'category': post['category'],
                    'description': post['description'],
                    'image': post.get('image'),
                    'excerpt': post['excerpt'],
                    'reading_time': post['reading_time']
                })

        # Save posts by tag
        tags_dir = self.output_dir / "tags"
        tags_dir.mkdir(exist_ok=True)
        for tag, tag_posts in tags_posts.items():
            tag_file = tags_dir / f"{tag.lower().replace(' ', '-')}.json"
            tag_data = {
                'tag': tag,
                'posts': sorted(tag_posts, key=lambda x: x['date'], reverse=True),
                'total': len(tag_posts)
            }
            with open(tag_file, 'w', encoding='utf-8') as f:
                json.dump(tag_data, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Generated {len(all_posts)} posts")
        print(f"✓ Generated {len(tags_posts)} tag files")
        print(f"✓ Output directory: {self.output_dir}")
        print("=" * 60)


def main():
    """Run the static generation."""
    generator = StaticPostGenerator()
    generator.run()


if __name__ == "__main__":
    main()