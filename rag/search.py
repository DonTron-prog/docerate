"""
Hybrid search implementation combining dense and sparse retrieval.
Uses Reciprocal Rank Fusion (RRF) to merge results.
"""

from typing import List, Dict, Optional, Tuple
import numpy as np
from dataclasses import dataclass

from .embeddings import EmbeddingStore, EmbeddingService
from .bm25 import BM25


@dataclass
class SearchResult:
    """Represents a search result with metadata."""
    chunk_id: str
    content: str
    score: float
    post_slug: str
    post_title: str
    section_heading: Optional[str]
    tags: List[str]
    url: str
    source_type: str  # 'dense', 'sparse', or 'hybrid'


class HybridSearch:
    """
    Hybrid search combining semantic (dense) and keyword (sparse) search.
    """

    def __init__(
        self,
        embedding_store: EmbeddingStore,
        embedding_service: EmbeddingService,
        bm25_model: BM25,
        chunks: List[Dict],
        alpha: float = 0.7
    ):
        """
        Initialize hybrid search.

        Args:
            embedding_store: Store for dense embeddings
            embedding_service: Service for generating query embeddings
            bm25_model: BM25 model for sparse retrieval
            chunks: List of chunk dictionaries with content and metadata
            alpha: Weight for dense retrieval (0-1, where 1 = only dense)
        """
        self.embedding_store = embedding_store
        self.embedding_service = embedding_service
        self.bm25_model = bm25_model
        self.chunks = chunks
        self.alpha = alpha

        # Create chunk ID to index mapping
        self.chunk_id_to_idx = {chunk['chunk_id']: i for i, chunk in enumerate(chunks)}

    def search(
        self,
        query: str,
        top_k: int = 10,
        filter_tags: Optional[List[str]] = None,
        rerank: bool = True
    ) -> List[SearchResult]:
        """
        Perform hybrid search.

        Args:
            query: Search query
            top_k: Number of results to return
            filter_tags: Optional tag filter
            rerank: Whether to apply reranking

        Returns:
            List of SearchResult objects
        """
        # Get dense retrieval results
        dense_results = self._dense_search(query, top_k * 2, filter_tags)

        # Get sparse retrieval results
        sparse_results = self._sparse_search(query, top_k * 2, filter_tags)

        # Merge results using RRF
        merged_results = self._reciprocal_rank_fusion(
            dense_results, sparse_results, top_k
        )

        # Optional reranking
        if rerank and len(merged_results) > 0:
            merged_results = self._rerank_results(query, merged_results, top_k)

        return merged_results

    def _dense_search(
        self,
        query: str,
        top_k: int,
        filter_tags: Optional[List[str]]
    ) -> List[Tuple[str, float]]:
        """
        Perform dense retrieval using embeddings.

        Returns:
            List of (chunk_id, score) tuples
        """
        # Generate query embedding
        query_embedding = self.embedding_service.embed_query(query)

        # Search in embedding store
        results = self.embedding_store.search(
            query_embedding,
            top_k=top_k,
            filter_tags=filter_tags
        )

        return [(r['chunk_id'], r['score']) for r in results]

    def _sparse_search(
        self,
        query: str,
        top_k: int,
        filter_tags: Optional[List[str]]
    ) -> List[Tuple[str, float]]:
        """
        Perform sparse retrieval using BM25.

        Returns:
            List of (chunk_id, score) tuples
        """
        # Search with BM25
        bm25_results = self.bm25_model.search(query, top_k=top_k * 2)

        # Apply tag filter if specified
        filtered_results = []
        for doc_idx, score in bm25_results:
            chunk = self.chunks[doc_idx]

            if filter_tags:
                if not any(tag in chunk.get('tags', []) for tag in filter_tags):
                    continue

            filtered_results.append((chunk['chunk_id'], score))

            if len(filtered_results) >= top_k:
                break

        return filtered_results

    def _reciprocal_rank_fusion(
        self,
        dense_results: List[Tuple[str, float]],
        sparse_results: List[Tuple[str, float]],
        top_k: int
    ) -> List[SearchResult]:
        """
        Merge results using Reciprocal Rank Fusion.

        RRF score = Σ(1 / (k + rank_i))
        where k is a constant (typically 60) and rank_i is the rank in list i
        """
        k = 60  # RRF constant
        scores = {}

        # Calculate RRF scores for dense results
        for rank, (chunk_id, _) in enumerate(dense_results):
            if chunk_id not in scores:
                scores[chunk_id] = {'dense': 0, 'sparse': 0, 'rrf': 0}
            scores[chunk_id]['dense'] = self.alpha / (k + rank + 1)

        # Calculate RRF scores for sparse results
        for rank, (chunk_id, _) in enumerate(sparse_results):
            if chunk_id not in scores:
                scores[chunk_id] = {'dense': 0, 'sparse': 0, 'rrf': 0}
            scores[chunk_id]['sparse'] = (1 - self.alpha) / (k + rank + 1)

        # Combine scores
        for chunk_id in scores:
            scores[chunk_id]['rrf'] = scores[chunk_id]['dense'] + scores[chunk_id]['sparse']

        # Sort by RRF score
        sorted_chunks = sorted(
            scores.items(),
            key=lambda x: x[1]['rrf'],
            reverse=True
        )[:top_k]

        # Create SearchResult objects
        results = []
        for chunk_id, score_dict in sorted_chunks:
            if chunk_id in self.chunk_id_to_idx:
                chunk = self.chunks[self.chunk_id_to_idx[chunk_id]]

                # Determine source type
                if score_dict['dense'] > 0 and score_dict['sparse'] > 0:
                    source_type = 'hybrid'
                elif score_dict['dense'] > 0:
                    source_type = 'dense'
                else:
                    source_type = 'sparse'

                result = SearchResult(
                    chunk_id=chunk_id,
                    content=chunk['content'],
                    score=score_dict['rrf'],
                    post_slug=chunk['post_slug'],
                    post_title=chunk['post_title'],
                    section_heading=chunk.get('section_heading'),
                    tags=chunk.get('tags', []),
                    url=f"/{chunk['post_slug']}{chunk.get('url_fragment', '')}",
                    source_type=source_type
                )
                results.append(result)

        return results

    def _rerank_results(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int
    ) -> List[SearchResult]:
        """
        Rerank results using a cross-encoder model (simplified version).
        In production, you would use a proper cross-encoder model.
        """
        # For now, we'll use a simple heuristic-based reranking
        # In production, use a cross-encoder like ms-marco-MiniLM-L-6-v2

        reranked = []
        for result in results:
            # Calculate relevance score based on:
            # 1. Query terms in content
            # 2. Query terms in title
            # 3. Section heading match

            query_terms = set(query.lower().split())
            content_terms = set(result.content.lower().split())
            title_terms = set(result.post_title.lower().split())

            # Term overlap scores
            content_overlap = len(query_terms & content_terms) / len(query_terms)
            title_overlap = len(query_terms & title_terms) / len(query_terms)

            # Section heading bonus
            section_bonus = 0
            if result.section_heading:
                section_terms = set(result.section_heading.lower().split())
                section_bonus = len(query_terms & section_terms) / len(query_terms) * 0.5

            # Combined rerank score
            rerank_score = (
                result.score * 0.4 +  # Original score
                content_overlap * 0.3 +  # Content relevance
                title_overlap * 0.2 +  # Title relevance
                section_bonus * 0.1  # Section relevance
            )

            result.score = rerank_score
            reranked.append(result)

        # Sort by new score
        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked[:top_k]