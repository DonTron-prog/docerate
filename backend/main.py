"""
Main FastAPI application for RAG-powered blog.
"""

import os
import sys
import time
import json
import pickle
import numpy as np
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from backend.config import settings, is_production
from backend.models import (
    SearchRequest, SearchResponse, SearchResult, ChunkMetadata,
    GenerateRequest, GenerateResponse, Reference,
    TagsResponse, TagInfo, HealthResponse, IndexStatus,
    PostSummary, PostDetail, PostListResponse, PostsByTagResponse
)
from backend.services.ollama import OllamaService
from backend.services.bedrock import BedrockService
from backend.services.openrouter import OpenRouterService
from backend.services.posts import PostService
from backend.services.data_loader import get_data_loader
from rag.search import HybridSearch
from rag.embeddings import EmbeddingStore, EmbeddingService, EmbeddingConfig
from rag.bm25 import BM25


# Global variables for storing loaded data
app_state = {
    "chunks": None,
    "embedding_store": None,
    "embedding_service": None,
    "bm25_model": None,
    "hybrid_search": None,
    "llm_service": None,
    "tags_cache": None,
    "index_status": None,
    "post_service": None
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    print("Starting up RAG API...")
    await load_search_index()
    await initialize_services()
    yield
    # Shutdown
    print("Shutting down RAG API...")


# Configure root_path for API Gateway stage prefix
stage = os.environ.get("STAGE", "")
root_path = f"/{stage}" if stage else ""

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
    root_path=root_path
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for images
image_candidates = []

if settings.image_dir:
    image_candidates.append(Path(settings.image_dir))

# Fallback paths for local development or legacy output structure
image_candidates.extend([
    Path(__file__).parent.parent / "content" / "images",
    Path(__file__).parent.parent / "output" / "images"
])

for images_path in image_candidates:
    if images_path.exists():
        app.mount("/images", StaticFiles(directory=str(images_path)), name="images")
        break


async def load_search_index():
    """Load search index artifacts using appropriate data loader."""
    print(f"Loading search index from {settings.data_source}...")
    data_loader = get_data_loader()

    try:
        # Check data source availability
        if not await data_loader.health_check():
            raise Exception(f"Data source {settings.data_source} is not available")

        # Load chunks
        app_state["chunks"] = await data_loader.load_chunks()
        print(f"Loaded {len(app_state['chunks'])} chunks")

        # Load embeddings
        embeddings = await data_loader.load_embeddings()
        metadata = await data_loader.load_metadata()

        # Create embedding store from loaded data
        store = EmbeddingStore(dimension=metadata['dimension'])
        store.embeddings = embeddings
        store.chunk_ids = metadata['chunk_ids']
        store.metadata = metadata['metadata']
        app_state["embedding_store"] = store
        print(f"Loaded embeddings")

        # Load BM25 model
        app_state["bm25_model"] = await data_loader.load_bm25_index()
        print(f"Loaded BM25 model")

        # Load index summary
        summary = await data_loader.load_index_summary()
        app_state["index_summary"] = summary or {}

        if summary and summary.get('created_at'):
            app_state["index_status"] = IndexStatus(
                last_updated=datetime.fromisoformat(summary['created_at']),
                num_posts=summary.get('num_posts', 0),
                num_chunks=summary.get('num_chunks', 0),
                embedding_model=summary.get('embedding_model', ''),
                tags=summary.get('tags', []),
                status="ready"
            )
        else:
            # Create status from loaded data
            app_state["index_status"] = IndexStatus(
                last_updated=datetime.now(),
                num_posts=len(set(c.get('post_slug') for c in app_state["chunks"])),
                num_chunks=len(app_state["chunks"]),
                embedding_model=settings.embedding_model,
                tags=list(set(tag for c in app_state["chunks"] for tag in c.get('tags', []))),
                status="ready"
            )

        # Extract tags for caching
        tags_count = {}
        for chunk in app_state["chunks"]:
            for tag in chunk.get('tags', []):
                tags_count[tag] = tags_count.get(tag, 0) + 1

        app_state["tags_cache"] = [
            TagInfo(name=tag, count=count)
            for tag, count in sorted(tags_count.items(), key=lambda x: x[1], reverse=True)
        ]

        print("Search index loaded successfully")

    except Exception as e:
        print(f"Failed to load search index: {e}")
        app_state["index_status"] = IndexStatus(
            last_updated=datetime.now(),
            num_posts=0,
            num_chunks=0,
            embedding_model="",
            tags=[],
            status="error"
        )
        raise


async def initialize_services():
    """Initialize LLM and embedding services."""
    print("Initializing services...")

    # Initialize embedding service
    embedding_config = EmbeddingConfig(
        provider=settings.embedding_provider,
        model_name=settings.embedding_model,
        dimension=settings.embedding_dimension
    )
    app_state["embedding_service"] = EmbeddingService(embedding_config)

    # Initialize LLM service based on provider
    llm_provider = settings.llm_provider.lower()
    if llm_provider == "bedrock":
        app_state["llm_service"] = BedrockService()
    elif llm_provider == "openrouter":
        app_state["llm_service"] = OpenRouterService()
    elif llm_provider == "ollama":
        app_state["llm_service"] = OllamaService()
    else:
        # Default based on environment
        if is_production():
            app_state["llm_service"] = BedrockService()
        else:
            app_state["llm_service"] = OpenRouterService()

    # Initialize post service
    app_state["post_service"] = PostService(
        content_dir=settings.content_dir,
        data_dir=settings.data_dir,
        image_base_url=settings.image_base_url,
        index_summary=app_state.get("index_summary")
    )

    # Initialize hybrid search
    app_state["hybrid_search"] = HybridSearch(
        embedding_store=app_state["embedding_store"],
        embedding_service=app_state["embedding_service"],
        bm25_model=app_state["bm25_model"],
        chunks=app_state["chunks"],
        alpha=settings.search_alpha
    )

    print("Services initialized")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    services_status = {
        "search_index": app_state["chunks"] is not None,
        "embeddings": app_state["embedding_store"] is not None,
        "llm": await app_state["llm_service"].health_check() if app_state["llm_service"] else False
    }

    return HealthResponse(
        status="healthy" if all(services_status.values()) else "degraded",
        environment=settings.environment,
        version=settings.api_version,
        timestamp=datetime.now(),
        services=services_status
    )


@app.get("/api/tags", response_model=TagsResponse)
async def get_tags():
    """Get all available tags."""
    if not app_state["tags_cache"]:
        raise HTTPException(status_code=503, detail="Tags not loaded")

    return TagsResponse(
        tags=app_state["tags_cache"],
        total_posts=app_state["index_status"].num_posts if app_state["index_status"] else 0,
        total_chunks=app_state["index_status"].num_chunks if app_state["index_status"] else 0
    )


@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """Perform hybrid search for relevant chunks."""
    start_time = time.time()

    if not app_state["hybrid_search"]:
        raise HTTPException(status_code=503, detail="Search service not available")

    try:
        # Perform search
        results = app_state["hybrid_search"].search(
            query=request.query,
            top_k=request.limit,
            filter_tags=request.tags if request.tags else None,
            rerank=request.rerank
        )

        # Convert to response model
        search_results = []
        for result in results:
            search_results.append(SearchResult(
                chunk_id=result.chunk_id,
                content=result.content,
                score=result.score,
                metadata=ChunkMetadata(
                    post_slug=result.post_slug,
                    post_title=result.post_title,
                    section_heading=result.section_heading,
                    tags=result.tags,
                    url_fragment=result.url,
                    position=0  # TODO: Add position from metadata
                ),
                source_type=result.source_type
            ))

        elapsed_ms = (time.time() - start_time) * 1000

        return SearchResponse(
            query=request.query,
            results=search_results,
            total_results=len(search_results),
            search_time_ms=elapsed_ms
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """Generate custom article based on query and context."""
    start_time = time.time()

    if not app_state["llm_service"]:
        raise HTTPException(status_code=503, detail="Generation service not available")

    # Validate that we have either a query or tags
    if not request.query and not request.tags:
        raise HTTPException(status_code=400, detail="Either a query or tags must be provided")

    try:
        # Create search query based on what's provided
        search_query = request.query if request.query else f"content about {', '.join(request.tags)}"

        # Search for relevant chunks
        search_results = app_state["hybrid_search"].search(
            query=search_query,
            top_k=10,
            filter_tags=request.tags if request.tags else None,
            rerank=True
        )

        # Build context from search results
        context_chunks = []
        references = []

        for i, result in enumerate(search_results):
            context_chunks.append(f"[Chunk {i+1}]\nTitle: {result.post_title}\nSection: {result.section_heading or 'Introduction'}\nContent: {result.content}\n")

            references.append(Reference(
                chunk_id=result.chunk_id,
                post_title=result.post_title,
                post_slug=result.post_slug,
                section_heading=result.section_heading,
                url=f"/{result.post_slug}{result.url}"
            ))

        # Build generation prompt
        context_text = "\n---\n".join(context_chunks)

        # Create appropriate prompt based on what was provided
        if request.query:
            generation_prompt = f"""Based on the following context from my blog posts, generate a comprehensive article addressing the user's query.

Context from blog posts:
{context_text}

User Query: {request.query}
Selected Topics: {', '.join(request.tags) if request.tags else 'All topics'}
Additional Requirements: {request.context if request.context else 'None'}

Generate an article that:
1. Directly addresses the user's query
2. Maintains my technical writing style
3. Includes specific examples and technical details from the context
4. References the source chunks where appropriate using [ref:N] notation
5. Flows naturally as a cohesive article, not just a collection of chunks

Article:"""
        else:
            # Tags-only generation
            generation_prompt = f"""Based on the following context from my blog posts, generate a comprehensive article about the selected topics.

Context from blog posts:
{context_text}

Selected Topics: {', '.join(request.tags)}
Additional Requirements: {request.context if request.context else 'None'}

Generate an article that:
1. Provides a comprehensive overview of the selected topics
2. Maintains my technical writing style
3. Includes specific examples and technical details from the context
4. References the source chunks where appropriate using [ref:N] notation
5. Flows naturally as a cohesive article, synthesizing the content meaningfully

Article:"""

        # Generate article
        article = await app_state["llm_service"].generate(
            prompt=generation_prompt,
            system_prompt=settings.generation_system_prompt,
            temperature=request.temperature or settings.generation_temperature,
            max_tokens=request.max_tokens or settings.generation_max_tokens
        )

        elapsed_ms = (time.time() - start_time) * 1000

        return GenerateResponse(
            article=article,
            references=references,
            generation_time_ms=elapsed_ms,
            model_used=settings.openrouter_model if settings.llm_provider == "openrouter" else (settings.llm_model if settings.llm_provider == "ollama" else settings.bedrock_model_id),
            chunks_retrieved=len(search_results)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate/stream")
async def generate_stream(request: GenerateRequest):
    """Stream generated content as it's created."""
    if not app_state["llm_service"]:
        raise HTTPException(status_code=503, detail="Generation service not available")

    # Validate that we have either a query or tags
    if not request.query and not request.tags:
        raise HTTPException(status_code=400, detail="Either a query or tags must be provided")

    async def stream_generator():
        try:
            # Create search query based on what's provided
            search_query = request.query if request.query else f"content about {', '.join(request.tags)}"

            # Search for relevant chunks (same as non-streaming)
            search_results = app_state["hybrid_search"].search(
                query=search_query,
                top_k=10,
                filter_tags=request.tags if request.tags else None,
                rerank=True
            )

            # Build context and references
            context_chunks = []
            references = []

            for i, result in enumerate(search_results):
                context_chunks.append(f"[Chunk {i+1}]\n{result.content}\n")
                references.append({
                    "chunk_id": result.chunk_id,
                    "post_title": result.post_title,
                    "url": f"/{result.post_slug}{result.url}"
                })

            # Send references first
            yield f"data: {json.dumps({'type': 'references', 'references': references})}\n\n"

            # Build and stream content
            context_text = "\n---\n".join(context_chunks)

            # Create appropriate prompt based on what was provided
            if request.query:
                generation_prompt = f"Context:\n{context_text}\n\nQuery: {request.query}\n\nGenerate article:"
            else:
                generation_prompt = f"Context:\n{context_text}\n\nTopics: {', '.join(request.tags)}\n\nGenerate a comprehensive article about these topics:"

            # Stream from LLM
            if hasattr(app_state["llm_service"], '_generate_stream'):
                async for chunk in app_state["llm_service"]._generate_stream(
                    prompt=generation_prompt,
                    system_prompt=settings.generation_system_prompt
                ):
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
            else:
                # Fallback to non-streaming
                article = await app_state["llm_service"].generate(
                    prompt=generation_prompt,
                    system_prompt=settings.generation_system_prompt
                )
                yield f"data: {json.dumps({'type': 'content', 'content': article})}\n\n"

            # Send done signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream"
    )


@app.get("/api/index/status", response_model=IndexStatus)
async def get_index_status():
    """Get the status of the search index."""
    if not app_state["index_status"]:
        raise HTTPException(status_code=503, detail="Index not loaded")

    return app_state["index_status"]


# Blog Post Endpoints

@app.get("/api/posts", response_model=PostListResponse)
async def get_posts(page: int = 1, per_page: int = 10):
    """Get all blog posts with pagination."""
    if not app_state["post_service"]:
        raise HTTPException(status_code=503, detail="Post service not initialized")

    all_posts = app_state["post_service"].get_all_posts()
    total = len(all_posts)

    # Calculate pagination
    start = (page - 1) * per_page
    end = start + per_page
    posts = all_posts[start:end]

    return PostListResponse(
        posts=posts,
        total=total,
        page=page,
        per_page=per_page,
        has_more=end < total
    )


@app.get("/api/posts/recent")
async def get_recent_posts(limit: int = 5):
    """Get recent blog posts."""
    if not app_state["post_service"]:
        raise HTTPException(status_code=503, detail="Post service not initialized")

    return app_state["post_service"].get_recent_posts(limit=limit)


@app.get("/api/posts/by-tag/{tag}", response_model=PostsByTagResponse)
async def get_posts_by_tag(tag: str):
    """Get all posts with a specific tag."""
    if not app_state["post_service"]:
        raise HTTPException(status_code=503, detail="Post service not initialized")

    posts = app_state["post_service"].get_posts_by_tag(tag)

    return PostsByTagResponse(
        tag=tag,
        posts=posts,
        total=len(posts)
    )


@app.get("/api/posts/{slug}", response_model=PostDetail)
async def get_post(slug: str):
    """Get a single post by slug."""
    if not app_state["post_service"]:
        raise HTTPException(status_code=503, detail="Post service not initialized")

    post = app_state["post_service"].get_post(slug)
    if not post:
        raise HTTPException(status_code=404, detail=f"Post '{slug}' not found")

    return PostDetail(**post)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5000,
        reload=True if settings.debug else False
    )
