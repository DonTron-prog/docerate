"""
Main indexing pipeline for processing blog posts into RAG-ready chunks.
"""

import os
import sys
import json
import yaml
import argparse
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from rag.chunker import MarkdownChunker
from rag.embeddings import EmbeddingConfig, EmbeddingService, EmbeddingStore
from rag.bm25 import BM25


class BlogIndexer:
    """Index blog posts for RAG retrieval."""

    def __init__(self, config_path: str = 'config.yaml'):
        """Initialize indexer with configuration."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.content_dir = Path(self.config['build']['content_dir'])
        self.data_dir = Path('data')
        self.data_dir.mkdir(exist_ok=True)

        # Initialize components
        self.chunker = MarkdownChunker(max_tokens=512, overlap_tokens=50)

        # Configure embedding service (default to local for development)
        embedding_config = EmbeddingConfig(
            provider=os.getenv('EMBEDDING_PROVIDER', 'local'),
            model_name=os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2'),
            dimension=384  # Will be updated based on model
        )
        self.embedding_service = EmbeddingService(embedding_config)
        self.embedding_store = EmbeddingStore(embedding_config.dimension)

    def load_posts(self) -> List[Dict[str, Any]]:
        """Load all markdown posts from content directory."""
        posts = []
        posts_dir = self.content_dir / 'posts'

        if not posts_dir.exists():
            print(f"Posts directory not found: {posts_dir}")
            return posts

        for filepath in posts_dir.glob('*.md'):
            print(f"Loading: {filepath.name}")

            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse frontmatter
            metadata = {}
            if content.startswith('---'):
                _, frontmatter, content = content.split('---', 2)
                metadata = yaml.safe_load(frontmatter)
                content = content.strip()

            # Set defaults
            metadata.setdefault('title', filepath.stem.replace('-', ' ').title())
            metadata.setdefault('tags', [])
            metadata.setdefault('category', 'general')

            # Normalize date
            if 'date' in metadata:
                if isinstance(metadata['date'], str):
                    try:
                        metadata['date'] = datetime.strptime(metadata['date'], '%Y-%m-%d')
                    except:
                        metadata['date'] = datetime.now()
                elif not isinstance(metadata['date'], datetime):
                    metadata['date'] = datetime.now()
            else:
                metadata['date'] = datetime.fromtimestamp(filepath.stat().st_mtime)

            posts.append({
                'filepath': str(filepath),
                'slug': filepath.stem,
                'content': content,
                'metadata': metadata
            })

        return posts

    def process_posts(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process posts into chunks."""
        all_chunks = []

        for post in posts:
            print(f"Processing: {post['metadata']['title']}")

            # Chunk the document
            chunks = self.chunker.chunk_document(
                content=post['content'],
                metadata=post['metadata'],
                post_slug=post['slug']
            )

            # Convert Chunk objects to dictionaries
            for chunk in chunks:
                chunk_dict = {
                    'chunk_id': chunk.chunk_id,
                    'content': chunk.content,
                    'post_slug': chunk.post_slug,
                    'post_title': chunk.post_title,
                    'section_heading': chunk.section_heading,
                    'tags': chunk.tags,
                    'url_fragment': chunk.url_fragment,
                    'position': chunk.position,
                    'token_count': chunk.token_count,
                    'date': post['metadata']['date'].isoformat()
                }
                all_chunks.append(chunk_dict)

        print(f"Created {len(all_chunks)} chunks from {len(posts)} posts")
        return all_chunks

    def generate_embeddings(self, chunks: List[Dict[str, Any]]):
        """Generate embeddings for all chunks."""
        print("Generating embeddings...")

        # Extract text content
        texts = [chunk['content'] for chunk in chunks]
        chunk_ids = [chunk['chunk_id'] for chunk in chunks]

        # Generate embeddings in batches
        batch_size = 32
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            print(f"Processing batch {i // batch_size + 1}/{(len(texts) + batch_size - 1) // batch_size}")

            batch_embeddings = self.embedding_service.embed_texts(batch_texts)
            all_embeddings.append(batch_embeddings)

        # Combine all embeddings
        if all_embeddings:
            embeddings = np.vstack(all_embeddings)
        else:
            embeddings = np.array([])

        # Store embeddings with metadata
        metadata = []
        for chunk in chunks:
            metadata.append({
                'post_slug': chunk['post_slug'],
                'post_title': chunk['post_title'],
                'section_heading': chunk['section_heading'],
                'tags': chunk['tags'],
                'url_fragment': chunk['url_fragment'],
                'position': chunk['position']
            })

        self.embedding_store.add_embeddings(embeddings, chunk_ids, metadata)
        print(f"Generated {len(embeddings)} embeddings")

    def build_bm25_index(self, chunks: List[Dict[str, Any]]) -> BM25:
        """Build BM25 index for keyword search."""
        print("Building BM25 index...")

        # Extract text content
        documents = [chunk['content'] for chunk in chunks]

        # Fit BM25
        bm25 = BM25()
        bm25.fit(documents)

        print(f"BM25 index built with {len(documents)} documents")
        return bm25

    def save_artifacts(self, chunks: List[Dict[str, Any]], bm25: BM25):
        """Save all artifacts to disk."""
        print("Saving artifacts...")

        # Save chunks
        chunks_path = self.data_dir / 'chunks.json'
        with open(chunks_path, 'w') as f:
            json.dump(chunks, f, indent=2, default=str)
        print(f"Saved chunks to {chunks_path}")

        # Save embeddings
        embeddings_path = self.data_dir / 'embeddings.npy'
        metadata_path = self.data_dir / 'metadata.json'
        self.embedding_store.save(str(embeddings_path), str(metadata_path))
        print(f"Saved embeddings to {embeddings_path}")

        # Save BM25 model
        bm25_path = self.data_dir / 'bm25_index.pkl'
        bm25.save(str(bm25_path))
        print(f"Saved BM25 index to {bm25_path}")

        # Generate index summary
        summary = {
            'created_at': datetime.now().isoformat(),
            'num_posts': len(set(c['post_slug'] for c in chunks)),
            'num_chunks': len(chunks),
            'embedding_model': self.embedding_service.config.model_name,
            'embedding_dimension': self.embedding_service.config.dimension,
            'chunk_config': {
                'max_tokens': self.chunker.max_tokens,
                'overlap_tokens': self.chunker.overlap_tokens
            },
            'tags': list(set(tag for c in chunks for tag in c['tags'])),
            'posts': [
                {
                    'slug': slug,
                    'title': next(c['post_title'] for c in chunks if c['post_slug'] == slug),
                    'num_chunks': len([c for c in chunks if c['post_slug'] == slug])
                }
                for slug in sorted(set(c['post_slug'] for c in chunks))
            ]
        }

        summary_path = self.data_dir / 'index_summary.json'
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"Saved index summary to {summary_path}")

    def run(self):
        """Run the complete indexing pipeline."""
        print("Starting indexing pipeline...")
        print("=" * 50)

        # Load posts
        posts = self.load_posts()
        if not posts:
            print("No posts found to index")
            return

        print(f"Found {len(posts)} posts")
        print("=" * 50)

        # Process into chunks
        chunks = self.process_posts(posts)
        print("=" * 50)

        # Generate embeddings
        self.generate_embeddings(chunks)
        print("=" * 50)

        # Build BM25 index
        bm25 = self.build_bm25_index(chunks)
        print("=" * 50)

        # Save artifacts
        self.save_artifacts(chunks, bm25)
        print("=" * 50)

        print("Indexing complete!")


def main():
    """Main entry point for indexing."""
    parser = argparse.ArgumentParser(description='Index blog posts for RAG')
    parser.add_argument('--config', default='config.yaml', help='Path to config file')
    parser.add_argument('--provider', choices=['local', 'bedrock'],
                       default='local', help='Embedding provider')
    parser.add_argument('--model', help='Embedding model name')

    args = parser.parse_args()

    # Set environment variables if specified
    if args.provider:
        os.environ['EMBEDDING_PROVIDER'] = args.provider
    if args.model:
        os.environ['EMBEDDING_MODEL'] = args.model

    # Run indexer
    indexer = BlogIndexer(args.config)
    indexer.run()


if __name__ == '__main__':
    main()