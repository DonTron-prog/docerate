#!/bin/bash

# Script to start the RAG blog locally

set -e

echo "==========================================
echo "Starting RAG Blog Local Development"
echo "=========================================="

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "Ollama is not installed. Please install it first:"
    echo "curl -fsSL https://ollama.com/install.sh | sh"
    exit 1
fi

# Pull required models if not present
echo "Checking Ollama models..."
if ! ollama list | grep -q "llama3.2"; then
    echo "Pulling llama3.2 model..."
    ollama pull llama3.2
fi

if ! ollama list | grep -q "nomic-embed-text"; then
    echo "Pulling nomic-embed-text model..."
    ollama pull nomic-embed-text
fi

# Create data directory if not exists
mkdir -p data

# Check if index exists
if [ ! -f "data/chunks.json" ]; then
    echo "No index found. Running indexer..."
    python scripts/index_posts.py
fi

# Start Ollama server in background
echo "Starting Ollama server..."
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to start
sleep 5

# Start FastAPI backend
echo "Starting FastAPI backend..."
cd backend
uvicorn main:app --reload --port 5000 &
BACKEND_PID=$!

echo "=========================================="
echo "Services started!"
echo "- API: http://localhost:5000"
echo "- API Docs: http://localhost:5000/docs"
echo "- Ollama: http://localhost:11434"
echo ""
echo "Press Ctrl+C to stop all services"
echo "=========================================="

# Function to cleanup on exit
cleanup() {
    echo "Stopping services..."
    kill $OLLAMA_PID 2>/dev/null
    kill $BACKEND_PID 2>/dev/null
    exit 0
}

# Set up trap to cleanup on Ctrl+C
trap cleanup INT

# Wait for background processes
wait