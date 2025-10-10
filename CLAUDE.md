# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Core Commands

### RAG System Development

```bash
# Set up environment
conda activate blog
pip install -r requirements.txt

# Build search index (required before running RAG)
python scripts/index_posts.py

# Start RAG backend (from project root)
PYTHONPATH=$PWD uvicorn backend.main:app --reload --port 5000 --host 0.0.0.0

# Start React frontend
cd rag-frontend
npm install  # First time only
npm start    # Runs on port 3000
```

### Docker Development

```bash
# Start all services
docker-compose up -d

# Build search index (first time)
docker-compose --profile indexing up indexer

# View logs
docker-compose logs -f backend
```

### Testing
```bash
# Currently no test suite - manual testing via local server
# Test RAG API at http://localhost:5000/docs
```

## Architecture Overview

This RAG-powered blog system transforms markdown blog posts into an interactive, AI-powered content generation platform. Users can search existing content and generate new articles based on your blog's knowledge base.

### RAG System Architecture
```
rag/              # Core RAG processing
├── indexer.py    # Creates embeddings and search index
├── chunker.py    # Smart markdown chunking (H2/H3 boundaries)
├── embeddings.py # Embedding generation (local/Bedrock)
├── bm25.py       # Keyword search implementation
└── search.py     # Hybrid search with RRF

backend/          # FastAPI application
├── main.py       # API endpoints and app lifecycle
├── models.py     # Pydantic models for API
├── config.py     # Environment configuration
└── services/     # LLM integrations (Ollama/Bedrock)
```

### Data Flow
1. **Indexing**: Markdown → Chunks → Embeddings + BM25 → `data/` directory
2. **Search**: Query → Hybrid Search (semantic + keyword) → Ranked chunks
3. **Generation**: Context chunks + Query → LLM → Streamed response

## Current Limitations

1. Lambda deployment needs manual configuration
2. Real-time index updates require backend restart

## Common Tasks

### Add New Blog Post
```bash
# Create new markdown file in content/posts/
# Format: YYYY-MM-DD-title.md with YAML frontmatter
python scripts/index_posts.py  # Update RAG index
# Restart backend to load new index
```

### Debug RAG Issues
```bash
# Check if index exists
ls -la data/

# Rebuild index if needed
python scripts/index_posts.py

# Test API directly
curl http://localhost:5000/health
curl http://localhost:5000/docs  # Interactive API docs
```

### Fix Import Errors
```bash
# Always run from project root
cd /home/donald/Projects/dontron_blog
export PYTHONPATH=$PWD
uvicorn backend.main:app --reload --port 5000
```

## Environment Configuration

### RAG System (.env file)
```bash
ENVIRONMENT=local
EMBEDDING_PROVIDER=local
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
SEARCH_ALPHA=0.7      # Semantic search weight (0=keyword only, 1=semantic only)
PYTHONPATH=$PWD       # Required for imports
```

## API Endpoints

- `POST /api/search` - Search blog content with optional tags
- `POST /api/generate` - Generate AI content based on context
- `GET /api/tags` - List available tags with counts
- `GET /health` - System health and index status

## AWS Deployment

### RAG System (Lambda)
- Use `backend/lambda_handler.py` for Lambda
- Requires Bedrock permissions for production
- Store index files in S3 for Lambda access
- use the conda environment blog