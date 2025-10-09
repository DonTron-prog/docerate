complete RAG-powered website using FastAPI that can run locally and deploy seamlessly to AWS. Here's the implementation 
    plan:

    Project Structure

    dontron_blog/
    ├── rag/                          # RAG processing modules
    │   ├── __init__.py
    │   ├── indexer.py               # Document chunking & indexing
    │   ├── embeddings.py            # Embedding generation
    │   ├── chunker.py               # Markdown section chunking
    │   ├── search.py                # Hybrid search implementation
    │   └── bm25.py                  # BM25 keyword search
    ├── backend/                      # FastAPI backend
    │   ├── __init__.py
    │   ├── main.py                  # FastAPI application
    │   ├── models.py                # Pydantic models
    │   ├── config.py                # Configuration
    │   ├── routers/
    │   │   ├── search.py            # Search endpoints
    │   │   ├── generate.py          # Generation endpoints
    │   │   └── tags.py              # Tag endpoints
    │   ├── services/
    │   │   ├── ollama.py            # Local LLM service
    │   │   ├── bedrock.py           # AWS Bedrock service
    │   │   └── embeddings.py        # Embedding service
    │   ├── lambda_handler.py        # AWS Lambda wrapper
    │   └── requirements.txt
    ├── rag-frontend/                 # React frontend
    │   ├── src/
    │   │   ├── components/
    │   │   │   ├── TagCloud.jsx
    │   │   │   ├── QueryInput.jsx
    │   │   │   ├── ArticleDisplay.jsx
    │   │   │   └── References.jsx
    │   │   ├── services/
    │   │   │   └── api.js
    │   │   └── App.jsx
    │   ├── package.json
    │   └── Dockerfile
    ├── data/                         # Processed data storage
    │   ├── chunks.json
    │   ├── embeddings.npy
    │   ├── metadata.json
    │   └── bm25_index.pkl
    ├── scripts/
    │   ├── index_posts.py           # Run indexing pipeline
    │   └── deploy_aws.sh            # Deploy to AWS
    ├── infrastructure/
    │   ├── terraform/
    │   │   ├── main.tf
    │   │   ├── lambda.tf
    │   │   ├── api_gateway.tf
    │   │   └── s3.tf
    │   └── cloudformation/
    │       └── rag-stack.yaml
    ├── docker-compose.yml
    ├── Dockerfile.backend
    ├── Dockerfile.indexer
    └── .env.example

    Implementation Steps

    1. RAG Indexing Pipeline (rag/indexer.py)

    - Parse markdown posts with frontmatter
    - Chunk by H2/H3 sections (max 512 tokens)
    - Preserve sentence boundaries
    - Extract metadata (title, tags, date, URL fragments)
    - Generate embeddings using sentence-transformers locally
    - Calculate BM25 statistics for keyword search
    - Save as JSON/pickle files for fast loading

    2. FastAPI Backend (backend/main.py)

    # Core endpoints:
    GET  /api/tags           - Get available tags
    POST /api/search         - Hybrid search for chunks
    POST /api/generate       - Generate custom article
    POST /api/generate/stream - Stream generation response
    GET  /docs              - Interactive API documentation
    GET  /health            - Health check for monitoring

    Features:
    - Async/await for concurrent operations
    - Pydantic models for validation
    - CORS middleware for frontend access
    - Environment-based configuration (local vs AWS)
    - Automatic switching between Ollama (local) and Bedrock (AWS)

    3. Hybrid Search Implementation (rag/search.py)

    - Dense retrieval: Cosine similarity on embeddings
    - Sparse retrieval: BM25 keyword matching
    - Reciprocal Rank Fusion (RRF) for result merging
    - Tag filtering for topic selection
    - Reranking with cross-encoder model
    - Return top-k chunks with metadata

    4. React Frontend (rag-frontend/)

    Components:
    - TagCloud: D3.js interactive visualization
    - QueryInput: Text input with autocomplete
    - ArticleDisplay: Markdown renderer with syntax highlighting
    - References: Collapsible source citations

    Features:
    - Real-time search preview
    - Loading states and error handling
    - Responsive design
    - Dark mode support
    - Export generated articles

    5. Local Development Setup

    # Start all services locally
    docker-compose up -d

    # Or run individually:
    # Terminal 1: Ollama
    ollama serve
    ollama pull llama3.2
    ollama pull nomic-embed-text

    # Terminal 2: FastAPI
    cd backend
    uvicorn main:app --reload --port 5000

    # Terminal 3: React
    cd rag-frontend
    npm start

    6. AWS Deployment Configuration

    Lambda Function (backend/lambda_handler.py):
    from mangum import Mangum
    from main import app
    handler = Mangum(app)

    Environment Variables:
    - ENVIRONMENT: local/production
    - EMBEDDING_MODEL: local/bedrock
    - LLM_SERVICE: ollama/bedrock
    - S3_BUCKET: for production data storage
    - BEDROCK_MODEL_ID: claude-3-haiku/titan-embed

    API Gateway:
    - REST API with Lambda proxy integration
    - Custom domain: api.donaldmcgillivray.com
    - CORS configuration
    - Rate limiting and API keys

    7. CI/CD Pipeline Updates

    Add to .github/workflows/deploy.yml:
    - name: Index blog posts
      run: |
        python scripts/index_posts.py
        
    - name: Upload RAG artifacts
      run: |
        aws s3 sync data/ s3://${{ secrets.RAG_BUCKET }}/data/
        
    - name: Deploy Lambda function
      run: |
        cd backend
        zip -r function.zip .
        aws lambda update-function-code \
          --function-name rag-api \
          --zip-file fileb://function.zip

    8. Infrastructure as Code (Terraform)

    - S3 buckets for data and frontend
    - Lambda functions with appropriate IAM roles
    - API Gateway with custom domain
    - CloudFront distribution
    - Route 53 DNS configuration
    - CloudWatch logging and monitoring

    Key Features

    1. Seamless Local/AWS Switching:
      - Same codebase for both environments
      - Environment variables control service selection
      - Docker compose for local orchestration
    2. Performance Optimizations:
      - In-memory caching of embeddings (<50MB)
      - Async operations for concurrent processing
      - CDN caching for static assets
      - Lambda provisioned concurrency for cold starts
    3. Monitoring & Observability:
      - CloudWatch metrics and logs
      - X-Ray tracing for latency analysis
      - Custom metrics for search relevance
      - A/B testing framework ready
    4. Security:
      - API key authentication
      - Rate limiting
      - Input validation with Pydantic
      - CORS properly configured
      - Secrets management with AWS Secrets Manager

    Development Timeline

    - Day 1-2: Set up project structure and RAG indexing pipeline
    - Day 3-4: Implement FastAPI backend with local Ollama integration
    - Day 5-6: Create React frontend with core components
    - Day 7-8: Add hybrid search and reranking
    - Day 9-10: Docker setup and local testing
    - Day 11-12: AWS deployment configuration and Lambda wrapper
    - Day 13-14: Infrastructure as code and CI/CD pipeline
    - Day 15: Testing, optimization, and documentation

    This implementation provides a production-ready RAG system that works locally with Ollama and deploys seamlessly to AWS with Bedrock.