"""
Main FastAPI application for RAG-powered blog.
"""

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

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from backend.config import settings, is_production
from backend.models import (
    SearchRequest, SearchResponse, SearchResult, ChunkMetadata,
    GenerateRequest, GenerateResponse, Reference,
    TagsResponse, TagInfo, HealthResponse, IndexStatus
)
from backend.services.ollama import OllamaService
from backend.services.bedrock import BedrockService
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
    "index_status": None
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


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def load_search_index():
    """Load search index artifacts from disk."""
    print("Loading search index...")
    data_dir = Path(settings.data_dir)

    try:
        # Load chunks
        chunks_path = data_dir / settings.chunks_file
        with open(chunks_path, 'r') as f:
            app_state["chunks"] = json.load(f)
        print(f"Loaded {len(app_state['chunks'])} chunks")

        # Load embeddings
        embeddings_path = data_dir / settings.embeddings_file
        metadata_path = data_dir / settings.metadata_file
        app_state["embedding_store"] = EmbeddingStore.load(
            str(embeddings_path),
            str(metadata_path)
        )
        print(f"Loaded embeddings")

        # Load BM25 model
        bm25_path = data_dir / settings.bm25_file
        app_state["bm25_model"] = BM25.load(str(bm25_path))
        print(f"Loaded BM25 model")

        # Load index summary
        summary_path = data_dir / 'index_summary.json'
        if summary_path.exists():
            with open(summary_path, 'r') as f:
                summary = json.load(f)
                app_state["index_status"] = IndexStatus(
                    last_updated=datetime.fromisoformat(summary['created_at']),
                    num_posts=summary['num_posts'],
                    num_chunks=summary['num_chunks'],
                    embedding_model=summary['embedding_model'],
                    tags=summary['tags'],
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

    # Initialize LLM service
    if is_production():
        app_state["llm_service"] = BedrockService()
    else:
        app_state["llm_service"] = OllamaService()

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
            model_used=settings.llm_model if not is_production() else settings.bedrock_model_id,
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5000,
        reload=True if settings.debug else False
    )