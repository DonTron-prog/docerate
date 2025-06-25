---
title: "Welcome to My New Website: Backend Decitions for a Python-Powered Static Site"
date: 2024-01-15
tags: [python, web-development, static-site, aws]
category: announcement
description: "Introducing my new site built with a custom static site generator, featuring markdown support, code highlighting, and fast performance."
image: "blog-hero.jpg"
---

# Welcome

I'd like to introduce you to this new site, powered by a custom-built static site generator. I developed this platform using Python (the language I know best) and chose to host it on AWS S3, aiming for a balance of simplicity and functionality.

## Why I Built My Own Static Site Generator

There are many excellent options available however I had specific requirements that led me to create my own solution. I wanted a platform that would:

1. Give me complete control over both layout and functionality
2. Remain minimal and fast without requiring JavaScript frameworks
3. Integrate seamlessly with my existing AWS infrastructure
4. Support all the technical blogging features I need

![System Architecture Diagram](system_arch_diagram.png)
## Key Features
### Markdown Support

I can write in markdown with comprehensive support for:

- Code blocks with syntax highlighting
- Tables for structured data
- Images with automatic optimization
- Task lists for project tracking
- Footnotes for additional context[^1]

### Code Highlighting

Here's an example of the Python code that converts markdown to HTML:

```python
def parse_markdown(content):
    """Convert markdown content to HTML with extensions."""
    md = markdown.Markdown(extensions=[
        'codehilite',
        'tables',
        'fenced_code',
        'footnotes',
        'toc'
    ])
    return md.convert(content)
```

### Table Support

The system supports GitHub-flavored markdown tables, making it easy to present structured data:

| Feature | Description | Status |
|---------|-------------|--------|
| Markdown parsing | Convert .md files to HTML | ✅ Complete |
| Syntax highlighting | Beautiful code blocks | ✅ Complete |
| Image optimization | Automatic thumbnail generation | ✅ Complete |
| Search | Client-side search with JSON index | ✅ Complete |
| RSS Feed | For feed readers | 🚧 Coming soon |

### Task Lists

Track project progress with task lists:

- [x] Set up Python project structure
- [x] Implement markdown parser
- [x] Create responsive templates
- [x] Add syntax highlighting
- [ ] Implement RSS feed
- [ ] Add sitemap generation

## Technical Implementation

The generator is built with just a few Python dependencies:

```python
# Core dependencies
markdown==3.5.1          # Markdown parsing
pymdown-extensions==10.5 # Extended markdown features
jinja2==3.1.2           # Template engine
pygments==2.17.2        # Syntax highlighting
pillow==10.2.0          # Image processing
```

### The Build Process

My build process follows a straightforward workflow:

1. Parse markdown files with YAML frontmatter
2. Generate HTML using Jinja2 templates
3. Optimize images and create thumbnails
4. Build search index as JSON
5. Deploy to S3 via GitHub Actions
![The build process flow](build_process.png)
### Performance Metrics

The site performs quite well across several key metrics:

| Metric | Result |
|--------|--------|
| Build time | ~1 second for 100 posts |
| Page size | <50KB including CSS |
| Time to interactive | <500ms with CDN |
| Lighthouse score | 100/100 |

## AWS Infrastructure

I've implemented a simple but effective AWS setup:

```yaml
Infrastructure:
  Storage: S3 bucket with static hosting
  CDN: CloudFront for global distribution
  DNS: Route 53 for domain management
  Deployment: GitHub Actions CI/CD
```

## Future Plans

I have several features planned for future development:

1. RSS feed for subscribers
2. Dark mode toggle
3. Comments via GitHub discussions
4. Analytics with privacy-friendly tracking
5. Newsletter integration

## Source Code Availability

The entire static site generator is open source. You can use it for your own blog or as inspiration for building your own tools. Check out the [GitHub repository](#) for installation instructions and documentation.

---

Thanks for reading. I look forward to sharing more technical content, tutorials, and insights on this platform. Stay tuned for posts about Python, AWS, web development, and more.

[^1]: I love markdown! I can edit it in any application including mobile, it's simple but has all the formatting I need without bloat, and most importantly I can write and edit using keyboard shortcuts like code.