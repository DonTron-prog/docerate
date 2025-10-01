"""
Pydantic models for request/response validation.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# Request Models

class SearchRequest(BaseModel):
    """Request model for search endpoint."""
    query: str = Field(..., description="Search query text", min_length=1)
    tags: Optional[List[str]] = Field(default=[], description="Filter by tags")
    limit: int = Field(default=5, description="Number of results to return", ge=1, le=20)
    rerank: bool = Field(default=True, description="Apply reranking to results")


class GenerateRequest(BaseModel):
    """Request model for content generation."""
    query: Optional[str] = Field(default="", description="User query or topic (optional)")
    tags: List[str] = Field(default=[], description="Selected topic tags")
    context: Optional[str] = Field(default="", description="Additional context or requirements")
    max_tokens: Optional[int] = Field(default=2048, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(default=0.7, description="Generation temperature", ge=0, le=1)
    stream: bool = Field(default=False, description="Stream the response")


class ReindexRequest(BaseModel):
    """Request model for triggering reindexing."""
    force: bool = Field(default=False, description="Force full reindex even if up to date")


# Response Models

class ChunkMetadata(BaseModel):
    """Metadata for a chunk."""
    post_slug: str
    post_title: str
    section_heading: Optional[str]
    tags: List[str]
    url_fragment: str
    position: int


class SearchResult(BaseModel):
    """Individual search result."""
    chunk_id: str
    content: str
    score: float = Field(..., ge=0, le=1)
    metadata: ChunkMetadata
    source_type: str = Field(..., description="Source of result: dense, sparse, or hybrid")


class SearchResponse(BaseModel):
    """Response for search endpoint."""
    query: str
    results: List[SearchResult]
    total_results: int
    search_time_ms: float


class Reference(BaseModel):
    """Reference to source content."""
    chunk_id: str
    post_title: str
    post_slug: str
    section_heading: Optional[str]
    url: str


class GenerateResponse(BaseModel):
    """Response for content generation."""
    article: str
    references: List[Reference]
    generation_time_ms: float
    model_used: str
    chunks_retrieved: int


class StreamChunk(BaseModel):
    """Single chunk for streaming responses."""
    type: str = Field(..., description="Type of chunk: content, reference, or done")
    content: Optional[str] = None
    reference: Optional[Reference] = None
    done: bool = Field(default=False)


class TagInfo(BaseModel):
    """Information about a tag."""
    name: str
    count: int
    description: Optional[str] = None


class TagsResponse(BaseModel):
    """Response for tags endpoint."""
    tags: List[TagInfo]
    total_posts: int
    total_chunks: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    environment: str
    version: str
    timestamp: datetime
    services: Dict[str, bool]


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None


class IndexStatus(BaseModel):
    """Status of the search index."""
    last_updated: datetime
    num_posts: int
    num_chunks: int
    embedding_model: str
    tags: List[str]
    status: str = Field(..., description="Status: ready, indexing, or error")


# Blog Post Models

class PostSummary(BaseModel):
    """Summary of a blog post for list views."""
    slug: str
    title: str
    date: str
    tags: List[str]
    category: str
    description: str
    image: Optional[str]
    excerpt: str
    reading_time: int = Field(..., description="Estimated reading time in minutes")


class PostDetail(BaseModel):
    """Full blog post with content."""
    slug: str
    title: str
    date: str
    tags: List[str]
    category: str
    description: str
    image: Optional[str]
    content: str = Field(..., description="Raw markdown content")
    html_content: str = Field(..., description="Rendered HTML content")
    reading_time: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PostListResponse(BaseModel):
    """Response for post list endpoints."""
    posts: List[PostSummary]
    total: int
    page: int = Field(default=1)
    per_page: int = Field(default=10)
    has_more: bool = Field(default=False)


class PostsByTagResponse(BaseModel):
    """Response for posts filtered by tag."""
    tag: str
    posts: List[PostSummary]
    total: int