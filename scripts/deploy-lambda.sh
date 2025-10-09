#!/bin/bash
set -e

# Script to package and deploy Lambda function
# Creates a minimal deployment package using requirements-lambda.txt

echo "==================================="
echo "Deploying Lambda Function"
echo "==================================="

# Configuration
FUNCTION_NAME=${LAMBDA_FUNCTION_NAME:-"rag-blog-api"}
AWS_REGION=${AWS_REGION:-"us-east-1"}
AWS_PROFILE=${AWS_PROFILE:-"default"}
S3_BUCKET=${S3_BUCKET:-"your-rag-data-bucket"}
LAMBDA_ROLE=${LAMBDA_ROLE:-""}
RUNTIME="python3.11"
MEMORY_SIZE=512
TIMEOUT=30

LLM_PROVIDER_VALUE=${LLM_PROVIDER:-"openrouter"}
EMBEDDING_PROVIDER_VALUE=${EMBEDDING_PROVIDER:-"bedrock"}
BEDROCK_MODEL_ID_VALUE=${BEDROCK_MODEL_ID:-"anthropic.claude-3-haiku-20240307-v1:0"}
BEDROCK_EMBEDDING_MODEL_VALUE=${BEDROCK_EMBEDDING_MODEL:-"amazon.titan-embed-text-v2:0"}
EMBEDDING_MODEL_VALUE=${EMBEDDING_MODEL:-$BEDROCK_EMBEDDING_MODEL_VALUE}
DATA_DIR_VALUE=${DATA_DIR:-"/tmp/rag_data"}
CONTENT_DIR_VALUE=${CONTENT_DIR:-"content/posts"}
IMAGE_DIR_VALUE=${IMAGE_DIR:-"content/images"}
IMAGE_BASE_URL_VALUE=${IMAGE_BASE_URL:-"/images"}
STAGE_VALUE=${STAGE:-"prod"}
OPENROUTER_API_KEY_VALUE=${OPENROUTER_API_KEY:-""}
OPENROUTER_MODEL_VALUE=${OPENROUTER_MODEL:-"meta-llama/llama-3.2-3b-instruct"}
OPENROUTER_SITE_URL_VALUE=${OPENROUTER_SITE_URL:-"https://docerate.com"}
OPENROUTER_APP_NAME_VALUE=${OPENROUTER_APP_NAME:-"DocerateRAG"}

# Check if Lambda role is provided
if [ -z "$LAMBDA_ROLE" ]; then
    echo "Error: LAMBDA_ROLE environment variable not set"
    echo "Usage: LAMBDA_ROLE=arn:aws:iam::123:role/lambda-role ./scripts/deploy-lambda.sh"
    echo ""
    echo "Create a role with these policies:"
    echo "  - AWSLambdaBasicExecutionRole"
    echo "  - AmazonS3ReadOnlyAccess"
    echo "  - AmazonBedrockFullAccess (if using Bedrock)"
    exit 1
fi

# Clean up previous build
echo "Cleaning up previous build..."
rm -rf lambda_package lambda_function.zip

# Create package directory
mkdir -p lambda_package

# Install Lambda dependencies
echo "Installing Lambda dependencies..."
pip install -q --target lambda_package -r requirements-lambda.txt

# Ensure NumPy stays in the Lambda layer to keep package small
for artifact in numpy numpy.libs; do
    if [ -e "lambda_package/$artifact" ]; then
        echo "Removing bundled $artifact in favour of Lambda layer..."
        rm -rf "lambda_package/$artifact"
    fi
done
find lambda_package -maxdepth 1 -type d -name "numpy-*.dist-info" -exec rm -rf {} +

# Copy application code
echo "Copying application code..."
cp -r backend lambda_package/
cp -r rag lambda_package/

# Include blog content assets for API responses
mkdir -p lambda_package/content
cp -r content/posts lambda_package/content/
cp -r content/images lambda_package/content/

# Remove unnecessary files
echo "Cleaning up package..."
find lambda_package -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find lambda_package -type f -name "*.pyc" -delete
find lambda_package -type f -name "*.pyo" -delete
find lambda_package -type f -name ".DS_Store" -delete

# Create deployment package
echo "Creating deployment package..."
cd lambda_package
zip -q -r ../lambda_function.zip . -x "*.pyc" "*.pyo" ".DS_Store" "__pycache__/*"
cd ..

# Check package size
PACKAGE_SIZE=$(du -h lambda_function.zip | cut -f1)
PACKAGE_BYTES=$(stat -f%z lambda_function.zip 2>/dev/null || stat -c%s lambda_function.zip)
MAX_SIZE=$((250 * 1024 * 1024))  # 250 MB

echo "Package size: $PACKAGE_SIZE"

if [ $PACKAGE_BYTES -gt $MAX_SIZE ]; then
    echo "Error: Package size exceeds Lambda limit (250 MB)"
    echo "Current size: $PACKAGE_SIZE"
    exit 1
fi

# Check if function exists
echo "Checking if Lambda function exists..."
if aws lambda get-function --function-name $FUNCTION_NAME \
    --profile $AWS_PROFILE --region $AWS_REGION > /dev/null 2>&1; then

    # Update existing function
    echo "Updating existing Lambda function..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://lambda_function.zip \
        --profile $AWS_PROFILE \
        --region $AWS_REGION > /dev/null

    echo "Waiting for code update to propagate..."
    aws lambda wait function-updated \
        --function-name $FUNCTION_NAME \
        --profile $AWS_PROFILE \
        --region $AWS_REGION

    # Update configuration
    echo "Updating function configuration..."

    CURRENT_ENV=$(aws lambda get-function-configuration \
        --function-name $FUNCTION_NAME \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        --query 'Configuration.Environment.Variables' \
        --output json 2>/dev/null || echo '{}')

    if [ -z "$OPENROUTER_API_KEY_VALUE" ]; then
        OPENROUTER_API_KEY_VALUE=$(echo "$CURRENT_ENV" | jq -r '.OPENROUTER_API_KEY // ""')
    fi

    if [ -z "$OPENROUTER_MODEL_VALUE" ]; then
        OPENROUTER_MODEL_VALUE=$(echo "$CURRENT_ENV" | jq -r '.OPENROUTER_MODEL // "meta-llama/llama-3.2-3b-instruct"')
    fi

    if [ -z "$OPENROUTER_SITE_URL_VALUE" ]; then
        OPENROUTER_SITE_URL_VALUE=$(echo "$CURRENT_ENV" | jq -r '.OPENROUTER_SITE_URL // "https://docerate.com"')
    fi

    if [ -z "$OPENROUTER_APP_NAME_VALUE" ]; then
        OPENROUTER_APP_NAME_VALUE=$(echo "$CURRENT_ENV" | jq -r '.OPENROUTER_APP_NAME // "DocerateRAG"')
    fi

    UPDATED_ENV=$(echo "$CURRENT_ENV" | jq \
        --arg env "production" \
        --arg datasource "s3" \
        --arg bucket "$S3_BUCKET" \
        --arg llm "$LLM_PROVIDER_VALUE" \
        --arg emb_provider "$EMBEDDING_PROVIDER_VALUE" \
        --arg bedrock_model "$BEDROCK_MODEL_ID_VALUE" \
        --arg bedrock_embedding "$BEDROCK_EMBEDDING_MODEL_VALUE" \
        --arg embedding_model "$EMBEDDING_MODEL_VALUE" \
        --arg data_dir "$DATA_DIR_VALUE" \
        --arg content_dir "$CONTENT_DIR_VALUE" \
        --arg image_dir "$IMAGE_DIR_VALUE" \
        --arg image_base "$IMAGE_BASE_URL_VALUE" \
        --arg stage "$STAGE_VALUE" \
        --arg openrouter_key "$OPENROUTER_API_KEY_VALUE" \
        --arg openrouter_model "$OPENROUTER_MODEL_VALUE" \
        --arg openrouter_site "$OPENROUTER_SITE_URL_VALUE" \
        --arg openrouter_app "$OPENROUTER_APP_NAME_VALUE" \
        --arg force_refresh "$(date +%s)" \
        '.ENVIRONMENT = $env |
         .DATA_SOURCE = $datasource |
         .S3_BUCKET = $bucket |
         .LLM_PROVIDER = $llm |
         .EMBEDDING_PROVIDER = $emb_provider |
         .BEDROCK_MODEL_ID = $bedrock_model |
         .BEDROCK_EMBEDDING_MODEL = $bedrock_embedding |
         .EMBEDDING_MODEL = $embedding_model |
         .DATA_DIR = $data_dir |
         .CONTENT_DIR = $content_dir |
         .IMAGE_DIR = $image_dir |
         .IMAGE_BASE_URL = $image_base |
         .STAGE = $stage |
         .OPENROUTER_API_KEY = $openrouter_key |
         .OPENROUTER_MODEL = $openrouter_model |
         .OPENROUTER_SITE_URL = $openrouter_site |
         .OPENROUTER_APP_NAME = $openrouter_app |
         .FORCE_REFRESH = $force_refresh'
    )

    ENV_PAYLOAD=$(echo "$UPDATED_ENV" | jq -c '{Variables: .}')

    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --handler backend.lambda_handler.lambda_handler \
        --memory-size $MEMORY_SIZE \
        --timeout $TIMEOUT \
        --environment "$ENV_PAYLOAD" \
        --profile $AWS_PROFILE \
        --region $AWS_REGION > /dev/null
else
    # Create new function
    echo "Creating new Lambda function..."
    ENV_PAYLOAD=$(jq -nc \
        --arg env "production" \
        --arg datasource "s3" \
        --arg bucket "$S3_BUCKET" \
        --arg llm "$LLM_PROVIDER_VALUE" \
        --arg emb_provider "$EMBEDDING_PROVIDER_VALUE" \
        --arg bedrock_model "$BEDROCK_MODEL_ID_VALUE" \
        --arg bedrock_embedding "$BEDROCK_EMBEDDING_MODEL_VALUE" \
        --arg embedding_model "$EMBEDDING_MODEL_VALUE" \
        --arg data_dir "$DATA_DIR_VALUE" \
        --arg content_dir "$CONTENT_DIR_VALUE" \
        --arg image_dir "$IMAGE_DIR_VALUE" \
        --arg image_base "$IMAGE_BASE_URL_VALUE" \
        --arg stage "$STAGE_VALUE" \
        --arg openrouter_key "$OPENROUTER_API_KEY_VALUE" \
        --arg openrouter_model "$OPENROUTER_MODEL_VALUE" \
        --arg openrouter_site "$OPENROUTER_SITE_URL_VALUE" \
        --arg openrouter_app "$OPENROUTER_APP_NAME_VALUE" \
        --arg force_refresh "$(date +%s)" \
        '{Variables: {
            ENVIRONMENT: $env,
            DATA_SOURCE: $datasource,
            S3_BUCKET: $bucket,
            LLM_PROVIDER: $llm,
            EMBEDDING_PROVIDER: $emb_provider,
            BEDROCK_MODEL_ID: $bedrock_model,
            BEDROCK_EMBEDDING_MODEL: $bedrock_embedding,
            EMBEDDING_MODEL: $embedding_model,
            DATA_DIR: $data_dir,
            CONTENT_DIR: $content_dir,
            IMAGE_DIR: $image_dir,
            IMAGE_BASE_URL: $image_base,
            STAGE: $stage,
            OPENROUTER_API_KEY: $openrouter_key,
            OPENROUTER_MODEL: $openrouter_model,
            OPENROUTER_SITE_URL: $openrouter_site,
            OPENROUTER_APP_NAME: $openrouter_app,
            FORCE_REFRESH: $force_refresh
        }}')

    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --role $LAMBDA_ROLE \
        --handler backend.lambda_handler.lambda_handler \
        --zip-file fileb://lambda_function.zip \
        --memory-size $MEMORY_SIZE \
        --timeout $TIMEOUT \
        --environment "$ENV_PAYLOAD" \
        --profile $AWS_PROFILE \
        --region $AWS_REGION > /dev/null
fi

# Wait for function to be active
echo "Waiting for function to be active..."
aws lambda wait function-active \
    --function-name $FUNCTION_NAME \
    --profile $AWS_PROFILE \
    --region $AWS_REGION

# Get function details
FUNCTION_ARN=$(aws lambda get-function --function-name $FUNCTION_NAME \
    --profile $AWS_PROFILE --region $AWS_REGION \
    --query 'Configuration.FunctionArn' --output text)

echo ""
echo "==================================="
echo "Lambda Deployment Complete!"
echo "==================================="
echo "Function: $FUNCTION_NAME"
echo "ARN: $FUNCTION_ARN"
echo "Memory: $MEMORY_SIZE MB"
echo "Timeout: $TIMEOUT seconds"
echo "Package size: $PACKAGE_SIZE"
echo ""
echo "Next steps:"
echo "1. Create API Gateway: aws apigateway create-rest-api --name rag-blog-api"
echo "2. Or use existing API Gateway and add Lambda integration"
echo "3. Test function: aws lambda invoke --function-name $FUNCTION_NAME response.json"

# Clean up
rm -rf lambda_package
