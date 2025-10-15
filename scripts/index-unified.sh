#!/bin/bash
set -e

# Unified RAG Indexing Script
# Supports multiple environments and embedding models
# Usage: ./scripts/index-unified.sh [environment] [--force]

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
ENVIRONMENT=${1:-local}
FORCE_REBUILD=false

for arg in "$@"; do
    if [ "$arg" = "--force" ]; then
        FORCE_REBUILD=true
    fi
done

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}RAG Unified Indexing Pipeline${NC}"
echo -e "${BLUE}======================================${NC}"

# Function to load environment file
load_env_file() {
    local env_file="$1"
    if [ -f "$env_file" ]; then
        echo -e "${GREEN}Loading environment from: $env_file${NC}"
        # Export variables from env file
        set -a
        source "$env_file"
        set +a
        return 0
    fi
    return 1
}

# Determine which environment file to load
ENV_FILE=""
case "$ENVIRONMENT" in
    local|dev|development)
        ENV_FILE=".env.local"
        if ! load_env_file "$ENV_FILE"; then
            ENV_FILE=".env"
            load_env_file "$ENV_FILE"
        fi
        echo -e "${GREEN}Environment: LOCAL DEVELOPMENT${NC}"
        ;;

    prod|production|aws)
        ENV_FILE=".env.production"
        if ! load_env_file "$ENV_FILE"; then
            echo -e "${RED}Error: Production environment file not found: $ENV_FILE${NC}"
            exit 1
        fi
        echo -e "${YELLOW}Environment: PRODUCTION${NC}"
        ;;

    test|testing)
        ENV_FILE=".env.test"
        if ! load_env_file "$ENV_FILE"; then
            ENV_FILE=".env"
            load_env_file "$ENV_FILE"
        fi
        echo -e "${GREEN}Environment: TESTING${NC}"
        ;;

    *)
        echo -e "${RED}Unknown environment: $ENVIRONMENT${NC}"
        echo "Usage: $0 [local|dev|prod|test] [--force]"
        exit 1
        ;;
esac

# Display configuration
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  Embedding Provider: ${EMBEDDING_PROVIDER:-not set}"
echo "  Embedding Model: ${EMBEDDING_MODEL:-not set}"
echo "  AWS Region: ${AWS_REGION:-us-east-1}"
echo "  Output Directory: ${DATA_DIR:-data}"
echo ""

# Validate required environment variables
if [ -z "$EMBEDDING_PROVIDER" ] || [ -z "$EMBEDDING_MODEL" ]; then
    echo -e "${RED}Error: EMBEDDING_PROVIDER and EMBEDDING_MODEL must be set${NC}"
    echo "Please check your environment file: $ENV_FILE"
    exit 1
fi

# Check AWS credentials if using Bedrock
if [ "$EMBEDDING_PROVIDER" = "bedrock" ]; then
    echo -e "${BLUE}Checking AWS credentials...${NC}"
    if ! aws sts get-caller-identity > /dev/null 2>&1; then
        echo -e "${RED}Error: AWS credentials not configured${NC}"
        echo "Please run: aws configure"
        exit 1
    fi
    echo -e "${GREEN}✓ AWS credentials configured${NC}"

    # Verify Bedrock access
    echo -e "${BLUE}Verifying Bedrock access...${NC}"
    if ! aws bedrock list-foundation-models --region "${AWS_REGION:-us-east-1}" > /dev/null 2>&1; then
        echo -e "${YELLOW}Warning: Unable to list Bedrock models. You may not have access.${NC}"
        echo "Please ensure you have access to: $EMBEDDING_MODEL"
    else
        echo -e "${GREEN}✓ Bedrock access confirmed${NC}"
    fi
fi

# Check if index already exists
if [ -d "${DATA_DIR:-data}" ] && [ -f "${DATA_DIR:-data}/embeddings.npy" ] && [ "$FORCE_REBUILD" != "true" ]; then
    echo ""
    echo -e "${YELLOW}Index already exists in ${DATA_DIR:-data}/${NC}"
    echo -e "${YELLOW}Use --force to rebuild the index${NC}"

    # Check if existing index matches current configuration
    if [ -f "${DATA_DIR:-data}/index_summary.json" ]; then
        EXISTING_MODEL=$(python -c "import json; print(json.load(open('${DATA_DIR:-data}/index_summary.json'))['embedding_model'])" 2>/dev/null || echo "unknown")
        if [ "$EXISTING_MODEL" != "$EMBEDDING_MODEL" ]; then
            echo -e "${RED}Warning: Existing index uses different model: $EXISTING_MODEL${NC}"
            echo -e "${RED}Current configuration expects: $EMBEDDING_MODEL${NC}"
            echo -e "${RED}You should rebuild with --force or update your configuration${NC}"
        else
            echo -e "${GREEN}Existing index matches configuration: $EXISTING_MODEL${NC}"
        fi
    fi
    exit 0
fi

# Activate conda environment if needed
if [ -n "$CONDA_DEFAULT_ENV" ] && [ "$CONDA_DEFAULT_ENV" != "blog" ]; then
    echo -e "${BLUE}Switching to blog conda environment...${NC}"
    source ~/anaconda3/etc/profile.d/conda.sh
    conda activate blog
fi

# Set Python path
export PYTHONPATH="${PYTHONPATH:-$PWD}"

# Run the indexing pipeline
echo ""
echo -e "${BLUE}Starting indexing pipeline...${NC}"
echo "Running: python scripts/index_posts.py"

python scripts/index_posts.py

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}Indexing Complete!${NC}"
    echo -e "${GREEN}======================================${NC}"

    # Display summary
    if [ -f "${DATA_DIR:-data}/index_summary.json" ]; then
        echo ""
        echo -e "${BLUE}Index Summary:${NC}"
        python -c "
import json
summary = json.load(open('${DATA_DIR:-data}/index_summary.json'))
print(f\"  Created: {summary['created_at']}\")
print(f\"  Model: {summary['embedding_model']}\")
print(f\"  Dimensions: {summary.get('embedding_dimension', 'N/A')}\")
print(f\"  Posts: {summary['num_posts']}\")
print(f\"  Chunks: {summary['num_chunks']}\")
print(f\"  Tags: {len(summary.get('tags', []))}\")
"
    fi

    # Environment-specific instructions
    echo ""
    if [ "$ENVIRONMENT" = "prod" ] || [ "$ENVIRONMENT" = "production" ]; then
        echo -e "${YELLOW}Next steps for production:${NC}"
        echo "1. Upload to S3: ./scripts/deploy-data.sh"
        echo "2. Deploy Lambda: ./scripts/deploy-lambda.sh"
    else
        echo -e "${GREEN}Next steps for local development:${NC}"
        echo "1. Start backend: uvicorn backend.main:app --reload --port 5000"
        echo "2. Start frontend: cd rag-frontend && npm start"
    fi
else
    echo ""
    echo -e "${RED}======================================${NC}"
    echo -e "${RED}Indexing Failed!${NC}"
    echo -e "${RED}======================================${NC}"
    echo "Please check the error messages above"
    exit 1
fi