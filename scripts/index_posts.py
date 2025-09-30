#!/usr/bin/env python3
"""
Script to run the RAG indexing pipeline.
This processes all blog posts and creates the search index.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from rag.indexer import BlogIndexer


def main():
    """Run the indexing pipeline."""
    print("=" * 60)
    print("RAG Indexing Pipeline for Blog Posts")
    print("=" * 60)

    # Check if running in Docker or locally
    if os.getenv('DOCKER_CONTAINER'):
        print("Running in Docker container")
    else:
        print("Running locally")

    # Create indexer and run
    indexer = BlogIndexer()
    indexer.run()

    print("\n" + "=" * 60)
    print("Indexing complete! You can now start the API server.")
    print("=" * 60)


if __name__ == '__main__':
    main()