#!/bin/bash
set -e

# Script to upload RAG indexes to S3
# Run after index-local.sh to upload generated indexes

echo "==================================="
echo "Deploying RAG Data to S3"
echo "==================================="

# Configuration
S3_BUCKET=${S3_BUCKET:-"your-rag-data-bucket"}
AWS_REGION=${AWS_REGION:-"us-east-1"}
AWS_PROFILE=${AWS_PROFILE:-"default"}

# Check if S3 bucket is configured
if [ "$S3_BUCKET" == "your-rag-data-bucket" ]; then
    echo "Error: S3_BUCKET environment variable not set"
    echo "Usage: S3_BUCKET=my-bucket ./scripts/deploy-data.sh"
    exit 1
fi

# Check if data files exist
echo "Checking local data files..."
if [ ! -d "data" ]; then
    echo "Error: data/ directory not found"
    echo "Run ./scripts/index-local.sh first to generate indexes"
    exit 1
fi

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI not installed"
    exit 1
fi

# Check AWS credentials
echo "Checking AWS credentials..."
aws sts get-caller-identity --profile $AWS_PROFILE > /dev/null 2>&1 || {
    echo "Error: AWS credentials not configured"
    echo "Run: aws configure --profile $AWS_PROFILE"
    exit 1
}

# Create bucket if it doesn't exist (optional)
echo "Checking S3 bucket..."
if ! aws s3 ls "s3://$S3_BUCKET" --profile $AWS_PROFILE > /dev/null 2>&1; then
    echo "Creating S3 bucket: $S3_BUCKET"
    aws s3 mb "s3://$S3_BUCKET" --region $AWS_REGION --profile $AWS_PROFILE

    # Enable versioning for safety
    aws s3api put-bucket-versioning \
        --bucket $S3_BUCKET \
        --versioning-configuration Status=Enabled \
        --profile $AWS_PROFILE
fi

# Upload data files
echo ""
echo "Uploading RAG indexes to S3..."
echo "Bucket: s3://$S3_BUCKET"
echo ""

# Upload each file with progress
for file in chunks.json embeddings.npy bm25_index.pkl metadata.json index_summary.json; do
    if [ -f "data/$file" ]; then
        echo "Uploading $file..."
        aws s3 cp "data/$file" "s3://$S3_BUCKET/$file" \
            --profile $AWS_PROFILE \
            --region $AWS_REGION \
            --metadata "uploaded=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "✓ $file uploaded"
    else
        echo "⚠ Warning: data/$file not found, skipping"
    fi
done

# Verify uploads
echo ""
echo "Verifying uploads..."
aws s3 ls "s3://$S3_BUCKET/" --profile $AWS_PROFILE --region $AWS_REGION

# Calculate total size
TOTAL_SIZE=$(aws s3 ls "s3://$S3_BUCKET/" --profile $AWS_PROFILE --region $AWS_REGION --summarize | grep "Total Size" | cut -d: -f2)

echo ""
echo "==================================="
echo "Data Deployment Complete!"
echo "==================================="
echo "Bucket: s3://$S3_BUCKET"
echo "Region: $AWS_REGION"
echo "Total size:$TOTAL_SIZE bytes"
echo ""
echo "Lambda functions can now access this data by setting:"
echo "  DATA_SOURCE=s3"
echo "  S3_BUCKET=$S3_BUCKET"