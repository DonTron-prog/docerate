# Python Static Blog Generator

A minimal, fast static site generator built with Python for blogging with markdown files. Features code highlighting, tables, image optimization, and client-side search.

## Features

- 📝 Write posts in Markdown with frontmatter
- 🎨 Syntax highlighting for code blocks
- 📊 GitHub-flavored markdown tables
- 🖼️ Automatic image optimization
- 🔍 Client-side search
- 🏷️ Tags and categories
- ⚡ Lightning fast build times
- 🚀 AWS S3 deployment ready

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create a new post:**
   ```bash
   python generator.py new --title "My First Post"
   ```

3. **Build the site:**
   ```bash
   python generator.py build
   ```

4. **Preview locally:**
   ```bash
   python generator.py serve
   ```
   Visit http://localhost:8000

## Project Structure

```
├── content/
│   ├── posts/       # Your markdown blog posts
│   └── images/      # Images for posts
├── templates/       # HTML templates
├── static/          # CSS, JS, fonts
├── output/          # Generated site (git-ignored)
├── generator.py     # Main build script
└── config.yaml      # Site configuration
```

## Writing Posts

Create markdown files in `content/posts/` with frontmatter:

```markdown
---
title: "Your Post Title"
date: 2024-01-15
tags: [python, web]
category: tutorial
description: "Brief description for SEO"
image: "featured.jpg"
---

Your content here...
```

## Markdown Features

- **Code blocks** with syntax highlighting
- **Tables** (GitHub-flavored)
- **Task lists** with checkboxes
- **Footnotes** for references
- **Table of contents** (optional)

## Commands

- `python generator.py build` - Build the static site
- `python generator.py serve` - Serve locally on port 8000
- `python generator.py watch` - Auto-rebuild on changes
- `python generator.py new --title "Title"` - Create new post

## Configuration

Edit `config.yaml` to customize:

- Site title, author, description
- Date format
- Posts per page
- Social links
- Analytics

## Deployment

The site auto-deploys to AWS S3 on push to main branch via GitHub Actions.

### Manual deployment:
```bash
python generator.py build
aws s3 sync output/ s3://your-bucket-name --delete
```

## AWS Setup

1. Create S3 bucket with static website hosting
2. Add bucket policy for public access
3. Configure GitHub secrets:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

## CDN Setup (Optional)

For better performance, set up CloudFront:

1. Create CloudFront distribution
2. Point to S3 bucket as origin
3. Add `CLOUDFRONT_DISTRIBUTION_ID` to GitHub secrets
4. Enable invalidation in deploy workflow

## License

MIT