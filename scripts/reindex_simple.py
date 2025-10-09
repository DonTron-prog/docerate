#!/usr/bin/env python3
"""
Simple re-indexing script using Bedrock Titan V2 embeddings.
Uses existing chunks and regenerates embeddings only.
"""

import json
import boto3
import numpy as np
from pathlib import Path

def get_titan_embedding(text, bedrock_client):
    """Get embedding from Titan Text Embeddings V2."""
    body = json.dumps({
        "inputText": text[:8000],  # Titan has an 8k token limit
        "dimensions": 1024,
        "normalize": True
    })

    response = bedrock_client.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=body
    )

    result = json.loads(response['body'].read())
    return np.array(result['embedding'])

def main():
    print("Re-indexing with AWS Bedrock Titan Text Embeddings V2...")

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
        return 1

    # Load existing chunks
    data_dir = Path("data")
    print("\nLoading existing chunks...")
    with open(data_dir / "chunks.json", "r") as f:
        chunks = json.load(f)
    print(f"Loaded {len(chunks)} chunks")

    # Generate new embeddings
    print("\nGenerating new embeddings with Bedrock...")
    embeddings = []
    chunk_ids = []
    metadata = []

    for i, chunk in enumerate(chunks):
        if i % 10 == 0:
            print(f"  Processing chunk {i+1}/{len(chunks)}...")

        # Generate embedding for chunk content
        embedding = get_titan_embedding(chunk['content'], bedrock_runtime)
        embeddings.append(embedding)
        chunk_ids.append(chunk['chunk_id'])
        metadata.append(chunk.get('metadata', {}))

    embeddings_array = np.array(embeddings)
    print(f"Generated embeddings shape: {embeddings_array.shape}")

    # Save new embeddings
    print("\nSaving new embeddings...")
    np.save(data_dir / "embeddings.npy", embeddings_array)
    print(f"✓ Saved embeddings to {data_dir / 'embeddings.npy'}")

    # Update metadata with new dimensions
    metadata_dict = {
        "dimension": int(embeddings_array.shape[1]),
        "chunk_ids": chunk_ids,
        "metadata": metadata,
        "model": "amazon.titan-embed-text-v2:0",
        "total_chunks": len(chunks)
    }

    with open(data_dir / "metadata.json", "w") as f:
        json.dump(metadata_dict, f, indent=2)
    print(f"✓ Updated metadata to {data_dir / 'metadata.json'}")

    # Update index summary
    from datetime import datetime
    with open(data_dir / "index_summary.json", "r") as f:
        summary = json.load(f)

    summary.update({
        "created_at": datetime.now().isoformat(),
        "embedding_model": "amazon.titan-embed-text-v2:0",
        "embedding_dimensions": int(embeddings_array.shape[1])
    })

    with open(data_dir / "index_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"✓ Updated index summary")

    print(f"\n✅ Re-indexing complete!")
    print(f"   Total chunks: {len(chunks)}")
    print(f"   Embedding dimensions: {embeddings_array.shape[1]}")
    print(f"   Model: amazon.titan-embed-text-v2:0")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())