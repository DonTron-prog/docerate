#!/usr/bin/env python3
"""
Re-index blog content using AWS Bedrock Titan Text Embeddings V2.
This script generates new embeddings compatible with production Bedrock access.
"""

import json
import sys
import os
import boto3
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.chunker import MarkdownChunker
from rag.bm25 import BM25
from backend.services.posts import PostService

def get_titan_embedding(text, bedrock_client):
    """Get embedding from Titan Text Embeddings V2."""
    body = json.dumps({
        "inputText": text,
        "dimensions": 1024,  # Titan V2 supports 256, 512, or 1024 dimensions
        "normalize": True
    })

    response = bedrock_client.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=body
    )

    result = json.loads(response['body'].read())
    return np.array(result['embedding'])

def main():
    print("Re-indexing blog content with AWS Bedrock Titan Text Embeddings V2...")

    # Initialize Bedrock client
    bedrock_runtime = boto3.client(
        'bedrock-runtime',
        region_name='us-east-1'
    )

    # Test Bedrock access
    print("Testing Bedrock access...")
    try:
        test_embedding = get_titan_embedding("test", bedrock_runtime)
        print(f"✓ Bedrock access confirmed. Embedding dimensions: {len(test_embedding)}")
    except Exception as e:
        print(f"✗ Failed to access Bedrock: {e}")
        print("\nPlease ensure you have access to amazon.titan-embed-text-v2:0 in AWS Bedrock")
        return 1

    # Load posts
    print("\nLoading blog posts...")
    post_service = PostService()
    posts = post_service.get_all_posts()
    print(f"Found {len(posts)} posts")

    # Chunk posts
    print("\nChunking posts...")
    chunker = MarkdownChunker(
        max_tokens=512,
        overlap_tokens=50
    )

    all_chunks = []
    for post in posts:
        # Prepare metadata
        metadata = {
            "post_title": post.get("title", ""),
            "post_slug": post.get("slug", ""),
            "tags": post.get("tags", []),
            "date": post.get("date", "")
        }
        chunks = chunker.chunk_document(
            content=post.get("content", ""),
            metadata=metadata,
            post_slug=post.get("slug", "")
        )
        all_chunks.extend(chunks)
    print(f"Created {len(all_chunks)} chunks")

    # Generate embeddings
    print("\nGenerating embeddings with Bedrock...")
    embeddings = []
    chunk_ids = []
    metadata = []

    for i, chunk in enumerate(all_chunks):
        if i % 10 == 0:
            print(f"Processing chunk {i+1}/{len(all_chunks)}...")

        # Generate embedding
        embedding = get_titan_embedding(chunk.text, bedrock_runtime)
        embeddings.append(embedding)
        chunk_ids.append(chunk.chunk_id)
        metadata.append(chunk.metadata)

    embeddings_array = np.array(embeddings)
    print(f"Generated embeddings shape: {embeddings_array.shape}")

    # Create BM25 index
    print("\nCreating BM25 index...")
    texts = [chunk.text for chunk in all_chunks]
    bm25_model = BM25(texts)

    # Save all artifacts
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    print("\nSaving artifacts...")

    # Save embeddings
    np.save(data_dir / "embeddings.npy", embeddings_array)
    print(f"✓ Saved embeddings to {data_dir / 'embeddings.npy'}")

    # Save chunks
    chunks_data = [chunk.to_dict() for chunk in all_chunks]
    with open(data_dir / "chunks.json", "w") as f:
        json.dump(chunks_data, f, indent=2)
    print(f"✓ Saved chunks to {data_dir / 'chunks.json'}")

    # Save metadata
    metadata_dict = {
        "dimension": embeddings_array.shape[1],
        "chunk_ids": chunk_ids,
        "metadata": metadata,
        "model": "amazon.titan-embed-text-v2:0",
        "total_chunks": len(all_chunks),
        "total_posts": len(posts)
    }
    with open(data_dir / "metadata.json", "w") as f:
        json.dump(metadata_dict, f, indent=2)
    print(f"✓ Saved metadata to {data_dir / 'metadata.json'}")

    # Save BM25 index
    import pickle
    with open(data_dir / "bm25_index.pkl", "wb") as f:
        pickle.dump(bm25_model, f)
    print(f"✓ Saved BM25 index to {data_dir / 'bm25_index.pkl'}")

    # Save index summary
    from datetime import datetime
    summary = {
        "created_at": datetime.now().isoformat(),
        "num_posts": len(posts),
        "num_chunks": len(all_chunks),
        "embedding_model": "amazon.titan-embed-text-v2:0",
        "embedding_dimensions": embeddings_array.shape[1],
        "tags": list(set(tag for chunk in all_chunks for tag in chunk.metadata.get("tags", [])))
    }
    with open(data_dir / "index_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"✓ Saved index summary to {data_dir / 'index_summary.json'}")

    print("\n✅ Re-indexing complete! New embeddings are ready for deployment.")
    print(f"   Embedding dimensions: {embeddings_array.shape[1]}")
    print(f"   Model: amazon.titan-embed-text-v2:0")
    return 0

if __name__ == "__main__":
    sys.exit(main())