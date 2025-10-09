#!/bin/bash
set -e

# Script to build and deploy React frontend to S3/CloudFront
# Builds the React app and syncs to S3 bucket with CloudFront invalidation

echo "==================================="
echo "Deploying React Frontend"
echo "==================================="

# Configuration
FRONTEND_BUCKET=${FRONTEND_BUCKET:-"your-frontend-bucket"}
CLOUDFRONT_DIST_ID=${CLOUDFRONT_DIST_ID:-""}
AWS_REGION=${AWS_REGION:-"us-east-1"}
AWS_PROFILE=${AWS_PROFILE:-"default"}
API_URL=${REACT_APP_API_URL:-"https://your-api-gateway-url"}

# Check if bucket is configured
if [ "$FRONTEND_BUCKET" == "your-frontend-bucket" ]; then
    echo "Error: FRONTEND_BUCKET environment variable not set"
    echo "Usage: FRONTEND_BUCKET=my-frontend-bucket ./scripts/deploy-frontend.sh"
    exit 1
fi

# Check if we're in the right directory
if [ ! -d "rag-frontend" ]; then
    echo "Error: rag-frontend/ directory not found"
    echo "Must run from project root directory"
    exit 1
fi

# Build React app
echo "Building React application..."
cd rag-frontend

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Set API URL for production
export REACT_APP_API_URL=$API_URL

# Build for production
echo "Creating production build..."
npm run build

# Check if build was successful
if [ ! -d "build" ]; then
    echo "Error: Build failed - build/ directory not created"
    exit 1
fi

cd ..

# Create bucket if it doesn't exist
echo "Checking S3 bucket..."
if ! aws s3 ls "s3://$FRONTEND_BUCKET" --profile $AWS_PROFILE > /dev/null 2>&1; then
    echo "Creating S3 bucket: $FRONTEND_BUCKET"
    aws s3 mb "s3://$FRONTEND_BUCKET" --region $AWS_REGION --profile $AWS_PROFILE

    # Configure for static website hosting
    aws s3 website "s3://$FRONTEND_BUCKET" \
        --index-document index.html \
        --error-document error.html \
        --profile $AWS_PROFILE

    # Add bucket policy for public read access
    cat > /tmp/bucket-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::$FRONTEND_BUCKET/*"
        }
    ]
}
EOF

    aws s3api put-bucket-policy \
        --bucket $FRONTEND_BUCKET \
        --policy file:///tmp/bucket-policy.json \
        --profile $AWS_PROFILE
    rm /tmp/bucket-policy.json
fi

# Sync files to S3
echo "Deploying to S3..."
aws s3 sync rag-frontend/build/ "s3://$FRONTEND_BUCKET" \
    --delete \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --cache-control "public, max-age=31536000" \
    --exclude "index.html" \
    --exclude "*.json"

# Upload index.html and JSON files with no cache
aws s3 cp rag-frontend/build/index.html "s3://$FRONTEND_BUCKET/index.html" \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --cache-control "no-cache, no-store, must-revalidate" \
    --content-type "text/html"

aws s3 sync rag-frontend/build/ "s3://$FRONTEND_BUCKET" \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --cache-control "no-cache, no-store, must-revalidate" \
    --exclude "*" \
    --include "*.json"

# Invalidate CloudFront cache if configured
if [ ! -z "$CLOUDFRONT_DIST_ID" ]; then
    echo "Invalidating CloudFront cache..."
    aws cloudfront create-invalidation \
        --distribution-id $CLOUDFRONT_DIST_ID \
        --paths "/*" \
        --profile $AWS_PROFILE > /dev/null

    # Get CloudFront domain
    CLOUDFRONT_DOMAIN=$(aws cloudfront get-distribution \
        --id $CLOUDFRONT_DIST_ID \
        --profile $AWS_PROFILE \
        --query 'Distribution.DomainName' \
        --output text)

    FRONTEND_URL="https://$CLOUDFRONT_DOMAIN"
else
    # Get S3 website endpoint
    FRONTEND_URL="http://$FRONTEND_BUCKET.s3-website-$AWS_REGION.amazonaws.com"
fi

echo ""
echo "==================================="
echo "Frontend Deployment Complete!"
echo "==================================="
echo "Bucket: s3://$FRONTEND_BUCKET"
echo "URL: $FRONTEND_URL"
if [ ! -z "$CLOUDFRONT_DIST_ID" ]; then
    echo "CloudFront: $CLOUDFRONT_DIST_ID"
    echo "Cache invalidation in progress..."
fi
echo ""
echo "The frontend is now live at: $FRONTEND_URL"