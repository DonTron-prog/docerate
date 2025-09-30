"""
Embedding generation module with support for both local and AWS Bedrock models.
"""

import os
import json
import numpy as np
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
import hashlib


@dataclass
class EmbeddingConfig:
    """Configuration for embedding models."""
    provider: str  # 'local' or 'bedrock'
    model_name: str
    dimension: int
    batch_size: int = 32


class EmbeddingService:
    """Service for generating embeddings with multiple providers."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.model = None
        self._initialize_model()

    def _initialize_model(self):
        """Initialize the embedding model based on provider."""
        if self.config.provider == 'local':
            self._init_local_model()
        elif self.config.provider == 'bedrock':
            self._init_bedrock_client()
        else:
            raise ValueError(f"Unknown provider: {self.config.provider}")

    def _init_local_model(self):
        """Initialize local sentence-transformer model."""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.config.model_name)
            # Update dimension based on actual model
            self.config.dimension = self.model.get_sentence_embedding_dimension()
        except ImportError:
            raise ImportError("Please install sentence-transformers: pip install sentence-transformers")

    def _init_bedrock_client(self):
        """Initialize AWS Bedrock client."""
        try:
            import boto3
            self.bedrock_client = boto3.client(
                service_name='bedrock-runtime',
                region_name=os.getenv('AWS_REGION', 'us-east-1')
            )
        except ImportError:
            raise ImportError("Please install boto3: pip install boto3")

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            Numpy array of shape (n_texts, dimension)
        """
        if not texts:
            return np.array([])

        if self.config.provider == 'local':
            return self._embed_local(texts)
        elif self.config.provider == 'bedrock':
            return self._embed_bedrock(texts)

    def _embed_local(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings using local model."""
        embeddings = self.model.encode(
            texts,
            batch_size=self.config.batch_size,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        return embeddings

    def _embed_bedrock(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings using AWS Bedrock."""
        all_embeddings = []

        # Process in batches
        for i in range(0, len(texts), self.config.batch_size):
            batch = texts[i:i + self.config.batch_size]
            batch_embeddings = []

            for text in batch:
                # Prepare request based on model
                if 'titan' in self.config.model_name.lower():
                    request_body = {
                        "inputText": text
                    }
                    model_id = "amazon.titan-embed-text-v1"
                elif 'cohere' in self.config.model_name.lower():
                    request_body = {
                        "texts": [text],
                        "input_type": "search_document"
                    }
                    model_id = "cohere.embed-english-v3"
                else:
                    raise ValueError(f"Unsupported Bedrock model: {self.config.model_name}")

                # Call Bedrock
                response = self.bedrock_client.invoke_model(
                    modelId=model_id,
                    body=json.dumps(request_body)
                )

                # Parse response
                response_body = json.loads(response['body'].read())

                if 'titan' in self.config.model_name.lower():
                    embedding = response_body['embedding']
                elif 'cohere' in self.config.model_name.lower():
                    embedding = response_body['embeddings'][0]

                batch_embeddings.append(embedding)

            all_embeddings.extend(batch_embeddings)

        return np.array(all_embeddings)

    def embed_query(self, query: str) -> np.ndarray:
        """
        Generate embedding for a single query.

        Args:
            query: Query text

        Returns:
            Numpy array of shape (dimension,)
        """
        embeddings = self.embed_texts([query])
        return embeddings[0]


class EmbeddingStore:
    """Store and retrieve embeddings efficiently."""

    def __init__(self, dimension: int):
        self.dimension = dimension
        self.embeddings = None
        self.metadata = []
        self.chunk_ids = []

    def add_embeddings(self, embeddings: np.ndarray, chunk_ids: List[str], metadata: List[Dict]):
        """Add embeddings with associated metadata."""
        if self.embeddings is None:
            self.embeddings = embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, embeddings])

        self.chunk_ids.extend(chunk_ids)
        self.metadata.extend(metadata)

    def search(self, query_embedding: np.ndarray, top_k: int = 10,
               filter_tags: Optional[List[str]] = None) -> List[Dict]:
        """
        Search for similar embeddings.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filter_tags: Optional tag filter

        Returns:
            List of results with scores and metadata
        """
        if self.embeddings is None or len(self.embeddings) == 0:
            return []

        # Apply tag filter if specified
        if filter_tags:
            indices = []
            for i, meta in enumerate(self.metadata):
                if any(tag in meta.get('tags', []) for tag in filter_tags):
                    indices.append(i)

            if not indices:
                return []

            filtered_embeddings = self.embeddings[indices]
            filtered_metadata = [self.metadata[i] for i in indices]
            filtered_chunk_ids = [self.chunk_ids[i] for i in indices]
        else:
            filtered_embeddings = self.embeddings
            filtered_metadata = self.metadata
            filtered_chunk_ids = self.chunk_ids

        # Calculate cosine similarity
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        embeddings_norm = filtered_embeddings / np.linalg.norm(filtered_embeddings, axis=1, keepdims=True)
        similarities = np.dot(embeddings_norm, query_norm)

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        # Prepare results
        results = []
        for idx in top_indices:
            results.append({
                'chunk_id': filtered_chunk_ids[idx],
                'score': float(similarities[idx]),
                'metadata': filtered_metadata[idx]
            })

        return results

    def save(self, embeddings_file: str, metadata_file: str):
        """Save embeddings and metadata to disk."""
        if self.embeddings is not None:
            np.save(embeddings_file, self.embeddings)

        with open(metadata_file, 'w') as f:
            json.dump({
                'chunk_ids': self.chunk_ids,
                'metadata': self.metadata,
                'dimension': self.dimension
            }, f, indent=2)

    @classmethod
    def load(cls, embeddings_file: str, metadata_file: str) -> 'EmbeddingStore':
        """Load embeddings and metadata from disk."""
        embeddings = np.load(embeddings_file)

        with open(metadata_file, 'r') as f:
            data = json.load(f)

        store = cls(dimension=data['dimension'])
        store.embeddings = embeddings
        store.chunk_ids = data['chunk_ids']
        store.metadata = data['metadata']

        return store