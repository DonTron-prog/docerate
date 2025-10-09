"""
Service for loading and serving blog posts.
"""
import os
import json
import markdown
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import frontmatter
from functools import lru_cache

class PostService:
    """Service for managing blog post content."""

    def __init__(
        self,
        content_dir: str = "content/posts",
        data_dir: str = "data",
        image_base_url: Optional[str] = None,
        index_summary: Optional[Dict[str, Any]] = None
    ):
        """Initialize the post service.

        Args:
            content_dir: Directory containing markdown posts
            data_dir: Directory containing indexed data
        """
        self.content_dir = Path(content_dir)
        self.data_dir = Path(data_dir)
        self.image_base_url = image_base_url or "/images"
        self._index_summary = index_summary
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
        self._posts_cache: Dict[str, Dict[str, Any]] = {}
        self._load_post_metadata()

    def _load_post_metadata(self):
        """Load post metadata from index summary."""
        data: Optional[Dict[str, Any]] = None

        if self._index_summary:
            data = self._index_summary
        else:
            summary_path = self.data_dir / "index_summary.json"
            if summary_path.exists():
                with open(summary_path, 'r') as f:
                    data = json.load(f)

        if data:
            self.post_metadata = data.get('posts', {})
            self.tags = data.get('tags', {})
        else:
            self.post_metadata = {}
            self.tags = {}

    def _parse_post_filename(self, filename: str) -> Dict[str, Any]:
        """Extract metadata from post filename.

        Handles both formats:
        - YYYY-MM-DD-slug.md (preferred)
        - any-name.md (fallback)
        """
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
            'slug': slug,
            'filename': filename
        }

    @lru_cache(maxsize=32)
    def get_post(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get a single post by slug.

        Args:
            slug: Post slug (filename without date prefix and .md extension)

        Returns:
            Post data with content and metadata
        """
        # Check cache first
        if slug in self._posts_cache:
            return self._posts_cache[slug]

        # Find the post file
        post_file = None
        # Normalize slug for comparison
        normalized_slug = slug.lower().replace(' ', '-').replace('_', '-')

        for file_path in self.content_dir.glob("*.md"):
            file_info = self._parse_post_filename(file_path.name)
            if file_info['slug'] == normalized_slug:
                post_file = file_path
                break

        if not post_file or not post_file.exists():
            return None

        # Parse the post with frontmatter
        try:
            with open(post_file, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
        except Exception as e:
            print(f"Error loading post {post_file}: {e}")
            return None

        # Process content to fix image paths
        processed_content = self._process_image_paths(post.content)

        # Convert markdown to HTML
        html_content = self.md.convert(processed_content)
        self.md.reset()

        # Extract metadata
        file_info = self._parse_post_filename(post_file.name)

        # Build post data
        post_data = {
            'slug': slug,
            'title': post.metadata.get('title', slug.replace('-', ' ').title()),
            'date': str(post.metadata.get('date', file_info['date'])),
            'tags': post.metadata.get('tags', []),
            'category': post.metadata.get('category', 'Uncategorized'),
            'description': post.metadata.get('description', ''),
            'image': self._process_image_url(post.metadata.get('image') or ''),
            'content': processed_content,  # Use processed content with fixed image paths
            'html_content': html_content,
            'metadata': post.metadata,
            'reading_time': self._calculate_reading_time(post.content)
        }

        # Cache the post
        self._posts_cache[slug] = post_data

        return post_data

    def get_all_posts(self, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all posts, optionally filtered by tag.

        Args:
            tag: Optional tag to filter by

        Returns:
            List of post summaries sorted by date (newest first)
        """
        posts = []

        for file_path in sorted(self.content_dir.glob("*.md"), reverse=True):
            file_info = self._parse_post_filename(file_path.name)
            slug = file_info['slug']

            # Get full post data
            post_data = self.get_post(slug)
            if not post_data:
                continue

            # Filter by tag if specified
            if tag and tag not in post_data.get('tags', []):
                continue

            # Create summary (without full content for list view)
            summary = {
                'slug': slug,
                'title': post_data['title'],
                'date': post_data['date'],
                'tags': post_data['tags'],
                'category': post_data['category'],
                'description': post_data['description'],
                'image': post_data['image'],
                'reading_time': post_data['reading_time'],
                'excerpt': self._create_excerpt(post_data['content'])
            }

            posts.append(summary)

        # Sort by date (newest first)
        posts.sort(key=lambda x: x['date'], reverse=True)

        return posts

    def get_recent_posts(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the most recent posts.

        Args:
            limit: Maximum number of posts to return

        Returns:
            List of recent post summaries
        """
        all_posts = self.get_all_posts()
        return all_posts[:limit]

    def get_posts_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """Get all posts with a specific tag.

        Args:
            tag: Tag to filter by

        Returns:
            List of post summaries with the specified tag
        """
        return self.get_all_posts(tag=tag)

    def get_all_tags(self) -> Dict[str, int]:
        """Get all tags with their post counts.

        Returns:
            Dictionary of tag names to post counts
        """
        return self.tags

    def _calculate_reading_time(self, content: str) -> int:
        """Calculate estimated reading time in minutes.

        Args:
            content: Post content

        Returns:
            Estimated reading time in minutes
        """
        words = len(content.split())
        # Average reading speed: 200-250 words per minute
        minutes = max(1, round(words / 225))
        return minutes

    def _process_image_paths(self, content: str) -> str:
        """Process markdown content to fix image paths.

        Converts relative image paths to absolute URLs pointing to our server.

        Args:
            content: Raw markdown content

        Returns:
            Processed markdown with fixed image URLs
        """
        import re

        # Replace markdown image syntax ![alt](image.png) with full URL
        def replace_image(match):
            alt_text = match.group(1)
            image_path = match.group(2)

            # If already a full URL, leave it as is
            if image_path.startswith('http://') or image_path.startswith('https://'):
                return match.group(0)

            return f'![{alt_text}]({self._build_image_url(image_path)})'

        # Match markdown image syntax
        pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        processed = re.sub(pattern, replace_image, content)

        return processed

    def _process_image_url(self, image_url: str) -> str:
        """Process a single image URL.

        Args:
            image_url: Image URL from frontmatter

        Returns:
            Processed image URL
        """
        if not image_url:
            return ''

        # If already a full URL, leave it as is
        if image_url.startswith('http://') or image_url.startswith('https://'):
            return image_url

        return self._build_image_url(image_url)

    def _create_excerpt(self, content: str, max_length: int = 200) -> str:
        """Create an excerpt from post content.

        Args:
            content: Full post content
            max_length: Maximum excerpt length

        Returns:
            Post excerpt
        """
        # Remove markdown formatting for excerpt
        lines = content.split('\n')
        excerpt = ''

        for line in lines:
            # Skip headers, code blocks, etc.
            if line.strip() and not line.startswith('#') and not line.startswith('```'):
                excerpt += line + ' '
                if len(excerpt) >= max_length:
                    break

        # Truncate and add ellipsis if needed
        if len(excerpt) > max_length:
            excerpt = excerpt[:max_length].rsplit(' ', 1)[0] + '...'

        return excerpt.strip()

    def _build_image_url(self, image_path: str) -> str:
        """Construct an absolute or relative image URL based on configuration."""
        path = image_path.lstrip('/')
        base = (self.image_base_url or '').rstrip('/')

        if not base:
            return f"/images/{path}"

        if base.startswith('http://') or base.startswith('https://'):
            return f"{base}/{path}"

        if base.startswith('/'):
            return f"{base}/{path}"

        # Default to relative path under /images if base is something like "images"
        return f"/{base}/{path}"
