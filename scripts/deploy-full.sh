#!/bin/bash
set -e

# Complete deployment script for RAG Blog system
# Orchestrates data, Lambda, and frontend deployment

echo "============================================"
echo "Full RAG Blog System Deployment"
echo "============================================"
echo ""

# Load environment variables from .env.production if it exists
if [ -f ".env.production" ]; then
    echo "Loading configuration from .env.production..."
    export $(cat .env.production | grep -v '^#' | xargs)
fi

# Configuration with defaults
export S3_BUCKET=${S3_BUCKET:-"your-rag-data-bucket"}
export FRONTEND_BUCKET=${FRONTEND_BUCKET:-"your-frontend-bucket"}
export LAMBDA_FUNCTION_NAME=${LAMBDA_FUNCTION_NAME:-"rag-blog-api"}
export AWS_REGION=${AWS_REGION:-"us-east-1"}
export AWS_PROFILE=${AWS_PROFILE:-"default"}
export CLOUDFRONT_DIST_ID=${CLOUDFRONT_DIST_ID:-""}
export API_GATEWAY_ID=${API_GATEWAY_ID:-""}

# Check required variables
MISSING_VARS=""
if [ "$S3_BUCKET" == "your-rag-data-bucket" ]; then
    MISSING_VARS="$MISSING_VARS S3_BUCKET"
fi
if [ "$FRONTEND_BUCKET" == "your-frontend-bucket" ]; then
    MISSING_VARS="$MISSING_VARS FRONTEND_BUCKET"
fi
if [ -z "$LAMBDA_ROLE" ]; then
    MISSING_VARS="$MISSING_VARS LAMBDA_ROLE"
fi

if [ ! -z "$MISSING_VARS" ]; then
    echo "Error: Required environment variables not set:$MISSING_VARS"
    echo ""
    echo "Please set these variables in .env.production or export them:"
    echo "  export S3_BUCKET=my-rag-data-bucket"
    echo "  export FRONTEND_BUCKET=my-frontend-bucket"
    echo "  export LAMBDA_ROLE=arn:aws:iam::123:role/lambda-execution-role"
    exit 1
fi

# Function to check command status
check_status() {
    if [ $? -eq 0 ]; then
        echo "✓ $1 completed successfully"
    else
        echo "✗ $1 failed"
        exit 1
    fi
}

# Step 1: Build indexes locally (optional, skip if already built)
echo ""
echo "Step 1: Building RAG indexes..."
echo "--------------------------------"
if [ ! -f "data/embeddings.npy" ] || [ "$REBUILD_INDEX" == "true" ]; then
    ./scripts/index-local.sh
    check_status "Index building"
else
    echo "⚠ Indexes already exist, skipping build (set REBUILD_INDEX=true to rebuild)"
fi

# Step 2: Upload data to S3
echo ""
echo "Step 2: Deploying data to S3..."
echo "--------------------------------"
./scripts/deploy-data.sh
check_status "Data deployment"

# Step 3: Deploy Lambda function
echo ""
echo "Step 3: Deploying Lambda function..."
echo "-------------------------------------"
./scripts/deploy-lambda.sh
check_status "Lambda deployment"

# Step 4: Set up API Gateway (if ID provided)
if [ ! -z "$API_GATEWAY_ID" ]; then
    echo ""
    echo "Step 4: Configuring API Gateway..."
    echo "-----------------------------------"

    # Get Lambda ARN
    LAMBDA_ARN=$(aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME \
        --profile $AWS_PROFILE --region $AWS_REGION \
        --query 'Configuration.FunctionArn' --output text)

    # Add Lambda permission for API Gateway
    aws lambda add-permission \
        --function-name $LAMBDA_FUNCTION_NAME \
        --statement-id apigateway-invoke \
        --action lambda:InvokeFunction \
        --principal apigateway.amazonaws.com \
        --source-arn "arn:aws:execute-api:$AWS_REGION:*:$API_GATEWAY_ID/*/*/*" \
        --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null || true

    # Get API Gateway URL
    API_URL="https://$API_GATEWAY_ID.execute-api.$AWS_REGION.amazonaws.com/prod"
    export REACT_APP_API_URL=$API_URL

    echo "✓ API Gateway configured"
    echo "  API URL: $API_URL"
else
    echo ""
    echo "Step 4: Skipping API Gateway setup"
    echo "-----------------------------------"
    echo "⚠ No API_GATEWAY_ID provided"
    echo "  You'll need to manually create an API Gateway and connect it to Lambda"
    export REACT_APP_API_URL="https://your-api-gateway-url"
fi

# Step 5: Deploy frontend
echo ""
echo "Step 5: Deploying frontend..."
echo "------------------------------"
./scripts/deploy-frontend.sh
check_status "Frontend deployment"

# Final summary
echo ""
echo "============================================"
echo "Deployment Complete!"
echo "============================================"
echo ""
echo "Infrastructure Summary:"
echo "----------------------"
echo "✓ Data Bucket: s3://$S3_BUCKET"
echo "✓ Frontend Bucket: s3://$FRONTEND_BUCKET"
echo "✓ Lambda Function: $LAMBDA_FUNCTION_NAME"

if [ ! -z "$API_GATEWAY_ID" ]; then
    echo "✓ API Gateway: $API_URL"
else
    echo "⚠ API Gateway: Not configured (manual setup required)"
fi

if [ ! -z "$CLOUDFRONT_DIST_ID" ]; then
    CLOUDFRONT_URL="https://$(aws cloudfront get-distribution --id $CLOUDFRONT_DIST_ID \
        --profile $AWS_PROFILE --query 'Distribution.DomainName' --output text)"
    echo "✓ CloudFront: $CLOUDFRONT_URL"
else
    echo "✓ Frontend URL: http://$FRONTEND_BUCKET.s3-website-$AWS_REGION.amazonaws.com"
fi

echo ""
echo "Next Steps:"
echo "-----------"

if [ -z "$API_GATEWAY_ID" ]; then
    echo "1. Create API Gateway and connect to Lambda function"
    echo "   aws apigateway create-rest-api --name rag-blog-api"
fi

if [ -z "$CLOUDFRONT_DIST_ID" ]; then
    echo "2. Set up CloudFront distribution for better performance"
fi

echo "3. Configure custom domain (optional)"
echo "4. Test the deployment:"
echo "   - Frontend: $CLOUDFRONT_URL (or S3 website URL)"
echo "   - API Health: curl $API_URL/health"
echo ""
echo "Deployment log saved to: deployment-$(date +%Y%m%d-%H%M%S).log"