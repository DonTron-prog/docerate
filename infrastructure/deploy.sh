#!/bin/bash

# Deploy script for RAG infrastructure
set -e

echo "🚀 Deploying Dontron Blog RAG Infrastructure"

# Check prerequisites
command -v npm >/dev/null 2>&1 || { echo "npm is required but not installed. Aborting." >&2; exit 1; }
command -v aws >/dev/null 2>&1 || { echo "AWS CLI is required but not installed. Aborting." >&2; exit 1; }

# Install dependencies
echo "📦 Installing CDK dependencies..."
npm install

# Build TypeScript
echo "🔨 Building infrastructure code..."
npm run build

# Bootstrap CDK (only needs to be done once per account/region)
if [ "$1" == "--bootstrap" ]; then
    echo "🔧 Bootstrapping CDK..."
    npx cdk bootstrap
fi

# Synthesize CloudFormation templates
echo "📋 Synthesizing CloudFormation templates..."
npx cdk synth

# Deploy with optional parameters
if [ -n "$DOMAIN_NAME" ] && [ -n "$CERTIFICATE_ARN" ]; then
    echo "🌐 Deploying with custom domain: $DOMAIN_NAME"
    npx cdk deploy --all \
        --context domainName=$DOMAIN_NAME \
        --context certificateArn=$CERTIFICATE_ARN \
        --require-approval never
else
    echo "🚀 Deploying with default settings..."
    npx cdk deploy --all --require-approval never
fi

echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Upload RAG data to S3 bucket (check CloudFormation outputs for bucket name)"
echo "2. Access the frontend URL (check CloudFormation outputs)"
echo "3. Monitor Lambda logs in CloudWatch"
echo ""
echo "To destroy the infrastructure, run: npm run destroy"