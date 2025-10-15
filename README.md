# RAG-Powered Blog System

A Retrieval-Augmented Generation (RAG) system that transforms your static blog into an interactive, AI-powered content generation platform. Users can select topics and ask questions to receive custom-generated articles based on your existing blog content.

## Features

- **Hybrid Search**: Combines semantic (dense) and keyword (sparse) retrieval with Reciprocal Rank Fusion
- **Smart Chunking**: Preserves document structure by chunking at H2/H3 boundaries
- **Local Development**: Run entirely locally with Ollama for LLM inference
- **AWS Deployment Ready**: Seamlessly deploy to AWS Lambda with Bedrock
- **Interactive API**: FastAPI backend with automatic documentation
- **Streaming Support**: Real-time content generation with SSE

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  React Frontend │────▶│  FastAPI Backend │────▶│  LLM Service    │
│  (Port 3000)    │     │  (Port 5000)     │     │  (Ollama/Bedrock)│
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Search Index        │
                    │  - Embeddings        │
                    │  - BM25 Index        │
                    │  - Chunk Metadata    │
                    └──────────────────────┘
```

## Important: Unified Embedding Configuration

**New in Latest Version:** We now use the same embedding model for both local development and production to ensure consistency. See [Unified Workflow Documentation](docs/UNIFIED_WORKFLOW.md) for details.

- **Standard Model**: `amazon.titan-embed-text-v2:0` (AWS Bedrock)
- **Benefits**: Perfect dev/prod parity, no index compatibility issues
- **Quick Setup**: `cp .env.local .env && ./scripts/index-unified.sh local`

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- AWS CLI configured (for Bedrock embeddings)
- Docker (optional)

### Option 1: Local Development

1. **Install Ollama** (for local LLM):
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2
ollama pull nomic-embed-text
```

2. **Set up Python environment**:
```bash
# Using conda (recommended)
conda create -n blog python=3.11
conda activate blog

# Or using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install --upgrade sentence-transformers huggingface-hub
```

3. **Configure environment and build the search index**:
```bash
# Copy environment template
cp .env.local .env

# Configure AWS credentials if not already done
aws configure

# Build the search index with Bedrock embeddings
./scripts/index-unified.sh local
```
This will process your blog posts and create the search index in the `data/` directory using AWS Bedrock embeddings for dev/prod parity.

4. **Start the backend** (from project root):
```bash
# Make sure you're in the project root directory
PYTHONPATH=/path/to/dontron_blog uvicorn backend.main:app --reload --port 5000 --host 0.0.0.0

# Or if PYTHONPATH is already set
uvicorn backend.main:app --reload --port 5000
```

5. **Start the frontend** (in a new terminal):
```bash
cd rag-frontend
npm install  # First time only
npm start    # Runs on port 3000
```

6. **Access the application**:
- Frontend: http://localhost:3000
- API Docs: http://localhost:5000/docs

## Starting and Stopping Services

### Starting the Development Servers

**Prerequisites**: Make sure you have the RAG index built first:
```bash
# If data/ directory doesn't exist or you've updated posts
python -m rag.indexer
```

**Method 1: Using the blog conda environment (Recommended)**

1. **Start the Backend Server**:
```bash
# Activate conda environment and start backend
source ~/anaconda3/etc/profile.d/conda.sh
conda activate blog
export PYTHONPATH=$PWD
uvicorn backend.main:app --reload --port 5000 --host 0.0.0.0

# Or as a one-liner:
source ~/anaconda3/etc/profile.d/conda.sh && conda activate blog && export PYTHONPATH=$PWD && uvicorn backend.main:app --reload --port 5000 --host 0.0.0.0
```

2. **Start the Frontend Server** (in a new terminal):
```bash
cd rag-frontend
npm start
```

**Method 2: Using separate terminal windows**

Terminal 1 - Backend:
```bash
conda activate blog  # or source venv/bin/activate
export PYTHONPATH=/path/to/docerate
uvicorn backend.main:app --reload --port 5000 --host 0.0.0.0
```

Terminal 2 - Frontend:
```bash
cd rag-frontend
npm start
```

### Stopping the Services

**Option 1: Graceful shutdown**
- Press `Ctrl+C` in each terminal where the services are running

**Option 2: Force stop all services**
```bash
# Kill all uvicorn processes (backend)
pkill -f uvicorn

# Kill all npm/node processes (frontend)
pkill -f "npm start"

# Or kill by port if needed
lsof -i :5000 | grep LISTEN | awk '{print $2}' | xargs kill -9  # Backend
lsof -i :3000 | grep LISTEN | awk '{print $2}' | xargs kill -9  # Frontend
```

### Verifying Services are Running

Check if both servers are running correctly:
```bash
# Check which processes are listening on the ports
lsof -i :3000 -i :5000 | grep LISTEN

# Test backend health endpoint
curl http://localhost:5000/health

# Test frontend
curl -I http://localhost:3000
```

### Common Startup Issues and Solutions

**Backend fails to start:**
```bash
# Make sure you're in the project root
cd /path/to/docerate

# Ensure the blog conda environment is activated
conda activate blog

# Set PYTHONPATH explicitly
export PYTHONPATH=$PWD

# Check if data directory exists
ls -la data/
# If not, build the index:
python -m rag.indexer
```

**Frontend fails to start:**
```bash
# Make sure dependencies are installed
cd rag-frontend
npm ci  # or npm install

# If port 3000 is in use
PORT=3001 npm start  # Use a different port
```

**Services won't stop:**
```bash
# Find and kill processes by port
sudo lsof -t -i:5000 | xargs kill -9  # Backend
sudo lsof -t -i:3000 | xargs kill -9  # Frontend
```

### Running in Background (Optional)

To run services in the background and keep them running:

```bash
# Backend with nohup
nohup bash -c "source ~/anaconda3/etc/profile.d/conda.sh && conda activate blog && export PYTHONPATH=$PWD && uvicorn backend.main:app --reload --port 5000 --host 0.0.0.0" > backend.log 2>&1 &

# Frontend with nohup
cd rag-frontend
nohup npm start > frontend.log 2>&1 &

# Check logs
tail -f backend.log   # Backend logs
tail -f rag-frontend/frontend.log  # Frontend logs

# Stop background processes
jobs  # List background jobs
kill %1  # Kill job number 1
```

### Option 2: Docker Compose

1. **Build and start all services**:
```bash
docker-compose up -d
```

2. **Build the search index** (first time only):
```bash
docker-compose --profile indexing up indexer
```

3. **Access the services**:
- API: http://localhost:5000
- API Docs: http://localhost:5000/docs
- Frontend: http://localhost:3000 (when implemented)

## API Endpoints

### Search for Content
```bash
curl -X POST "http://localhost:5000/api/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "RAG implementation",
    "tags": ["AI", "RAG"],
    "limit": 5
  }'
```

### Generate Article
```bash
curl -X POST "http://localhost:5000/api/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I implement RAG with FastAPI?",
    "tags": ["RAG", "AI"],
    "context": "Focus on practical implementation details"
  }'
```

### Get Available Tags
```bash
curl "http://localhost:5000/api/tags"
```

## Project Structure

```
dontron_blog/
├── backend/               # FastAPI backend
│   ├── main.py           # Application entry point
│   ├── models.py         # Pydantic models
│   ├── config.py         # Configuration
│   └── services/         # LLM services
├── rag/                   # RAG processing modules
│   ├── indexer.py        # Main indexing pipeline
│   ├── chunker.py        # Document chunking
│   ├── embeddings.py     # Embedding generation
│   ├── bm25.py          # Keyword search
│   └── search.py        # Hybrid search
├── rag-frontend/         # React frontend
│   ├── src/             # Source code
│   ├── public/          # Static assets
│   └── package.json     # Node dependencies
├── content/              # Blog content
│   ├── posts/           # Markdown blog posts
│   └── images/          # Blog images
├── data/                 # Generated artifacts
│   ├── chunks.json      # Document chunks
│   ├── embeddings.npy   # Vector embeddings
│   ├── metadata.json    # Chunk metadata
│   └── bm25_index.pkl   # BM25 index
├── scripts/              # Utility scripts
│   ├── index_posts.py   # Build search index
│   └── start_local.sh   # Local dev helper
├── infrastructure/       # AWS deployment
├── docker-compose.yml    # Container orchestration
├── requirements.txt      # Python dependencies
└── .env                  # Environment config
```

## Configuration

Create a `.env` file (copy from `.env.example`):

```bash
# Environment
ENVIRONMENT=local

# Embedding Configuration
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=all-MiniLM-L6-v2

# LLM Configuration
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
OLLAMA_HOST=http://localhost:11434

# Search Configuration
SEARCH_ALPHA=0.7  # Weight for semantic search (0-1)
SEARCH_TOP_K=10
```

## AWS Deployment

### Deploy to Lambda

1. **Package the application**:
```bash
cd backend
zip -r function.zip .
```

2. **Deploy with AWS CLI**:
```bash
aws lambda create-function \
  --function-name rag-api \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-role \
  --handler lambda_handler.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 60 \
  --memory-size 1024
```

3. **Set environment variables**:
```bash
aws lambda update-function-configuration \
  --function-name rag-api \
  --environment Variables='{
    "ENVIRONMENT":"production",
    "EMBEDDING_PROVIDER":"bedrock",
    "LLM_PROVIDER":"bedrock",
    "S3_BUCKET":"your-rag-bucket"
  }'
```

## Development Workflow

### Adding New Blog Posts

1. Add markdown files to `content/posts/`
2. Re-run the indexer:
   ```bash
   python scripts/index_posts.py
   ```
3. Restart the backend to load new index

### Customizing Chunking Strategy

Edit `rag/chunker.py`:
```python
chunker = MarkdownChunker(
    max_tokens=512,      # Maximum tokens per chunk
    overlap_tokens=50    # Token overlap between chunks
)
```

### Adjusting Search Weights

Edit `backend/config.py` or set environment variable:
```bash
SEARCH_ALPHA=0.8  # More weight on semantic search
SEARCH_ALPHA=0.3  # More weight on keyword search
```

## Performance Optimization

### Indexing Tips
- Run indexing as a background job or CI/CD step
- Use GPU for faster embedding generation if available
- Cache embeddings for unchanged content

### Search Optimization
- Adjust `SEARCH_TOP_K` for speed vs quality tradeoff
- Enable reranking only when needed
- Use smaller embedding models for faster search

### Generation Optimization
- Use streaming for better UX
- Implement response caching for common queries
- Consider using smaller, faster models for simple queries

## Troubleshooting

### Common Issues

**Backend startup issues:**
```bash
# Make sure to start from the project root directory
cd /path/to/dontron_blog

# Set PYTHONPATH explicitly
export PYTHONPATH=$PWD

# Then start the server
uvicorn backend.main:app --reload --port 5000
```

**Sentence-transformers compatibility error:**
```bash
# Upgrade both packages to fix compatibility
pip install --upgrade sentence-transformers huggingface-hub
```

**Ollama not responding:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
ollama serve
```

**Import errors:**
```bash
# Ensure Python path is set
export PYTHONPATH=/path/to/dontron_blog:$PYTHONPATH
```

**Index not loading:**
```bash
# Check if data files exist
ls -la data/

# Rebuild index
python scripts/index_posts.py
```

**Port already in use:**
```bash
# Find and kill process using port 5000
lsof -i :5000
kill -9 <PID>

# Or use a different port
uvicorn backend.main:app --port 5001
```

## Next Steps

- [ ] Implement React frontend with tag cloud visualization
- [ ] Add user authentication and personalization
- [ ] Implement feedback loop for improving generation
- [ ] Add analytics and monitoring
- [ ] Create Terraform/CloudFormation templates
- [ ] Add support for multi-modal content

## License

This project is part of the dontron_blog repository.