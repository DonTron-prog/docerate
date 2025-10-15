# Unified RAG Development & Deployment Workflow

## Overview
This document describes the streamlined workflow for developing and deploying the RAG-powered blog system with consistent embedding models between local and production environments.

## Key Change: Dev/Prod Parity
We now use **the same embedding model** for both local development and AWS production to ensure consistency and prevent index compatibility issues.

**Standard Configuration:**
- **Embedding Model**: `amazon.titan-embed-text-v2:0` (1024 dimensions)
- **Provider**: AWS Bedrock
- **Benefits**: Perfect dev/prod parity, no index incompatibilities

## Environment Configuration

### 1. Local Development Setup

Copy the local environment template:
```bash
cp .env.local .env
```

The `.env.local` file is pre-configured to use Bedrock embeddings for dev/prod parity:
```ini
EMBEDDING_PROVIDER=bedrock
EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
EMBEDDING_DIMENSION=1024
```

**Prerequisites:**
- AWS CLI configured with credentials: `aws configure`
- Access to AWS Bedrock in your account
- Titan Embeddings V2 model enabled in Bedrock console

### 2. Production Configuration

The `.env.production` file uses the same embedding model:
```ini
EMBEDDING_PROVIDER=bedrock
EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
EMBEDDING_DIMENSION=1024
```

## Unified Indexing Script

The new `scripts/index-unified.sh` script automatically handles environment-specific configuration:

### Usage
```bash
# Local development (uses .env.local)
./scripts/index-unified.sh local

# Production build (uses .env.production)
./scripts/index-unified.sh prod

# Force rebuild existing index
./scripts/index-unified.sh local --force
```

### Features
- Automatically loads the correct environment file
- Validates AWS credentials for Bedrock
- Checks embedding model compatibility
- Provides clear error messages and guidance
- Prevents accidental model mismatches

## Complete Workflow

### Local Development

1. **Initial Setup**
   ```bash
   # Configure AWS credentials (one-time)
   aws configure

   # Copy and configure environment
   cp .env.local .env
   # Edit .env if needed
   ```

2. **Build RAG Index**
   ```bash
   # Build index with Bedrock embeddings
   ./scripts/index-unified.sh local
   ```

3. **Start Services**
   ```bash
   # Terminal 1: Start backend
   source ~/anaconda3/etc/profile.d/conda.sh
   conda activate blog
   export PYTHONPATH=$PWD
   uvicorn backend.main:app --reload --port 5000

   # Terminal 2: Start frontend
   cd rag-frontend
   npm start
   ```

### Production Deployment

1. **Build Production Index**
   ```bash
   # Use production environment
   ./scripts/index-unified.sh prod --force
   ```

2. **Deploy to S3**
   ```bash
   # Upload index files to S3
   ./scripts/deploy-data.sh
   ```
   The script validates that the index uses the correct embedding model before uploading.

3. **Deploy Lambda**
   ```bash
   # Package and deploy Lambda function
   ./scripts/deploy-lambda.sh
   ```

4. **Deploy Frontend**
   ```bash
   # Build and deploy React app
   ./scripts/deploy-frontend.sh
   ```

## Model Validation

The system now includes multiple validation points to prevent embedding model mismatches:

1. **Index Building**: The indexer validates dimensions match expected values
2. **Deployment**: `deploy-data.sh` checks the model before uploading to S3
3. **Runtime**: The backend validates index compatibility when loading

## Fallback for Offline Development

If you need to work offline without AWS access, you can switch to local embeddings:

1. Edit `.env`:
   ```ini
   EMBEDDING_PROVIDER=local
   EMBEDDING_MODEL=all-MiniLM-L6-v2
   EMBEDDING_DIMENSION=384
   ```

2. Rebuild the index:
   ```bash
   ./scripts/index-unified.sh local --force
   ```

**Note**: This index won't be compatible with production!

## Environment Variables Reference

| Variable | Description | Local Default | Production Default |
|----------|-------------|---------------|-------------------|
| `EMBEDDING_PROVIDER` | Provider for embeddings | bedrock | bedrock |
| `EMBEDDING_MODEL` | Model name | amazon.titan-embed-text-v2:0 | amazon.titan-embed-text-v2:0 |
| `EMBEDDING_DIMENSION` | Expected dimensions | 1024 | 1024 |
| `AWS_REGION` | AWS region for Bedrock | us-east-1 | us-east-1 |
| `S3_BUCKET` | S3 bucket for indexes | - | docerate-rag-data |

## Troubleshooting

### AWS Credentials Error
```bash
Error: AWS credentials not configured
```
**Solution**: Run `aws configure` and enter your AWS credentials.

### Bedrock Access Error
```bash
AccessDeniedException: Bedrock denied access to model
```
**Solution**: Enable the Titan Embeddings V2 model in the AWS Bedrock console for your region.

### Embedding Dimension Mismatch
```bash
Embedding dimension mismatch for amazon.titan-embed-text-v2:0!
Expected: 1024
Actual: 384
```
**Solution**: You're mixing embedding models. Ensure environment variables are set correctly and rebuild the index.

### Index Model Mismatch Warning
```bash
WARNING: Embedding model mismatch!
Index was built with: all-MiniLM-L6-v2
Production expects: amazon.titan-embed-text-v2:0
```
**Solution**: Rebuild the index with the production configuration:
```bash
./scripts/index-unified.sh prod --force
```

## Migration from Old Setup

If you have an existing index built with the old configuration:

1. **Check current model**:
   ```bash
   cat data/index_summary.json | grep embedding_model
   ```

2. **If using `all-MiniLM-L6-v2`**, rebuild with Bedrock:
   ```bash
   # Load production environment
   source .env.production

   # Rebuild index
   ./scripts/index-unified.sh prod --force

   # Deploy to S3
   ./scripts/deploy-data.sh
   ```

## Benefits of This Approach

1. **Dev/Prod Parity**: Same embeddings everywhere = no surprises
2. **Simplified Testing**: Local testing accurately represents production
3. **Reduced Errors**: Validation prevents incompatible indexes
4. **Clear Workflow**: One script handles all environments
5. **Better Documentation**: Environment files clearly show configuration

## Next Steps

1. Test the new workflow locally with Bedrock embeddings
2. Rebuild production index with verified configuration
3. Deploy and validate in production
4. Monitor for any embedding-related errors