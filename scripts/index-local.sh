#!/bin/bash
set -e

# Script to build RAG indexes locally
# This generates embeddings and BM25 index from blog posts

echo "==================================="
echo "Building RAG Indexes Locally"
echo "==================================="

# Check if we're in the right directory
if [ ! -f "requirements-indexing.txt" ]; then
    echo "Error: Must run from project root directory"
    exit 1
fi

# Activate conda environment if available
if command -v conda &> /dev/null; then
    echo "Activating conda environment..."
    source $(conda info --base)/etc/profile.d/conda.sh
    conda activate blog 2>/dev/null || true
fi

# Install indexing dependencies if needed
echo "Checking dependencies..."
pip install -q -r requirements-indexing.txt

# Set environment variables for local indexing
export ENVIRONMENT=local
export EMBEDDING_PROVIDER=local
export DATA_SOURCE=local
export PYTHONPATH=$PWD

# Run the indexer
echo "Building indexes from blog posts..."
python -m rag.indexer

# Verify the output
echo ""
echo "Verifying generated files..."
for file in data/chunks.json data/embeddings.npy data/bm25_index.pkl data/metadata.json data/index_summary.json; do
    if [ -f "$file" ]; then
        size=$(du -h "$file" | cut -f1)
        echo "✓ $file ($size)"
    else
        echo "✗ $file - MISSING!"
        exit 1
    fi
done

echo ""
echo "==================================="
echo "Indexing Complete!"
echo "==================================="
echo "Total size: $(du -sh data/ | cut -f1)"
echo ""
echo "You can now:"
echo "1. Test locally: python -m uvicorn backend.main:app --reload"
echo "2. Upload to S3: ./scripts/deploy-data.sh"