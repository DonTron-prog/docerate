# AWS Deployment Guide

Complete guide for deploying the Docerate RAG-powered blog on AWS.

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Step-by-Step Deployment](#step-by-step-deployment)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Updating the Deployment](#updating-the-deployment)

---

## Architecture Overview

The application uses a serverless architecture with unified CloudFront routing (no CORS):

```
User → CloudFront (d2w8hymo03zbys.cloudfront.net)
         ├─ /* → S3 (static blog content)
         └─ /api/* → API Gateway → Lambda → RAG Processing
                                          ↓
                                          S3 (RAG data)
                                          ↓
                                          Bedrock (embeddings)
                                          ↓
                                          OpenRouter (LLM)
```

**Key Components:**
- **S3 Buckets**: Static frontend + RAG data storage
- **CloudFront**: Global CDN with dual-origin routing (S3 + API Gateway)
  - **Single domain** for frontend and API = **No CORS needed!**
- **API Gateway**: HTTP API endpoint (accessed via CloudFront `/api/*`)
- **Lambda**: FastAPI application with Mangum adapter (no CORS middleware)
- **Lambda Layer**: NumPy for efficient vector operations
- **Bedrock**: AWS managed embeddings service
- **OpenRouter**: External LLM API for content generation

---

## Prerequisites

### Required Tools
```bash
# AWS CLI v2
aws --version  # Should be 2.x

# Python 3.11
python --version

# Node.js & npm (for frontend)
node --version
npm --version

# jq (for JSON processing in scripts)
jq --version
```

### AWS Account Setup
1. **AWS Account** with appropriate permissions
2. **AWS CLI** configured with credentials:
   ```bash
   aws configure
   # Use default profile or create a new one
   ```

3. **Required IAM Permissions**:
   - S3: CreateBucket, PutObject, GetObject, DeleteObject
   - Lambda: CreateFunction, UpdateFunctionCode, UpdateFunctionConfiguration
   - API Gateway: CreateApi, CreateRoute, CreateIntegration
   - CloudFront: CreateDistribution, CreateInvalidation
   - IAM: CreateRole, AttachRolePolicy
   - Bedrock: InvokeModel (for embeddings)

### External Services
- **OpenRouter Account**: Sign up at https://openrouter.ai/
  - Get API key from https://openrouter.ai/keys
  - Add credits to your account

---

## Initial Setup

### 1. Clone and Install Dependencies

```bash
# Clone repository
git clone <your-repo>
cd docerate

# Backend dependencies
conda create -n blog python=3.11
conda activate blog
pip install -r requirements.txt
pip install -r requirements-lambda.txt

# Frontend dependencies
cd rag-frontend
npm install
cd ..
```

### 2. Configure Environment Variables

Create `.env.production` in project root:

```bash
# Environment
ENVIRONMENT=production

# API Configuration
DEBUG=false
API_PREFIX=/api

# Data configuration
DATA_SOURCE=s3
S3_BUCKET=your-rag-data-bucket

# Embedding Configuration (MUST match index build)
EMBEDDING_PROVIDER=bedrock
EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
EMBEDDING_DIMENSION=1024
BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0

# LLM Configuration
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your-api-key-here
OPENROUTER_MODEL=meta-llama/llama-3.2-3b-instruct
OPENROUTER_SITE_URL=https://yourdomain.com
OPENROUTER_APP_NAME=Your App Name

# AWS Configuration
AWS_REGION=us-east-1

# Search Configuration
SEARCH_TOP_K=10
SEARCH_ALPHA=0.7
SEARCH_RERANK=true

# Generation Configuration
GENERATION_MAX_TOKENS=2048
GENERATION_TEMPERATURE=0.7

# Cache Configuration
ENABLE_CACHE=true
CACHE_TTL=3600
```

Create `rag-frontend/.env.production`:

```bash
# API URL is empty - uses relative URLs routed through CloudFront
REACT_APP_API_URL=
REACT_APP_ENVIRONMENT=production
```

---

## Step-by-Step Deployment

### Step 1: Create S3 Buckets

```bash
# Create frontend bucket
aws s3 mb s3://your-frontend-bucket

# Create RAG data bucket
aws s3 mb s3://your-rag-data-bucket

# Enable static website hosting on frontend bucket
aws s3 website s3://your-frontend-bucket \
    --index-document index.html \
    --error-document index.html
```

### Step 2: Create IAM Role for Lambda

```bash
# Create trust policy
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
    --role-name docerate-rag-lambda-role \
    --assume-role-policy-document file://trust-policy.json

# Attach AWS managed policies
aws iam attach-role-policy \
    --role-name docerate-rag-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam attach-role-policy \
    --role-name docerate-rag-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Create custom policy for Bedrock
cat > bedrock-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    }
  ]
}
EOF

aws iam create-policy \
    --policy-name docerate-bedrock-policy \
    --policy-document file://bedrock-policy.json

# Get your account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Attach custom policy
aws iam attach-role-policy \
    --role-name docerate-rag-lambda-role \
    --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/docerate-bedrock-policy
```

### Step 3: Create Lambda Layer (NumPy)

```bash
# Create layer directory
mkdir -p lambda-layers/numpy-layer/python

# Install NumPy for Lambda (Amazon Linux 2)
pip install numpy -t lambda-layers/numpy-layer/python

# Create layer package
cd lambda-layers/numpy-layer
zip -r ../numpy-layer.zip python
cd ../..

# Upload layer to AWS
aws lambda publish-layer-version \
    --layer-name docerate-numpy-layer \
    --zip-file fileb://lambda-layers/numpy-layer.zip \
    --compatible-runtimes python3.11 \
    --description "NumPy library for Lambda"

# Note the LayerVersionArn from output
```

### Step 4: Build and Deploy RAG Index

```bash
# Build the RAG index (uses Bedrock embeddings)
./scripts/index-unified.sh local --force

# Verify index files were created
ls -lh data/

# Deploy to S3
S3_BUCKET=your-rag-data-bucket ./scripts/deploy-data.sh
```

### Step 5: Create API Gateway

```bash
# Create HTTP API
aws apigatewayv2 create-api \
    --name docerate-rag-api \
    --protocol-type HTTP \
    --cors-configuration AllowOrigins='*',AllowMethods='*',AllowHeaders='*',MaxAge=3600

# Note the ApiId from output (e.g., 9o9ra1wg7f)
API_ID="your-api-id"

# Create integration (will update later with Lambda ARN)
# Save the API ID for later steps
```

### Step 6: Deploy Lambda Function

```bash
# Get the Lambda role ARN
LAMBDA_ROLE=$(aws iam get-role \
    --role-name docerate-rag-lambda-role \
    --query 'Role.Arn' --output text)

# Deploy Lambda
LAMBDA_FUNCTION_NAME=docerate-rag-api \
LAMBDA_ROLE=$LAMBDA_ROLE \
S3_BUCKET=your-rag-data-bucket \
EMBEDDING_PROVIDER=bedrock \
EMBEDDING_MODEL=amazon.titan-embed-text-v2:0 \
BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0 \
LLM_PROVIDER=openrouter \
OPENROUTER_API_KEY="your-api-key" \
./scripts/deploy-lambda.sh

# Attach Lambda layer
LAYER_ARN=$(aws lambda list-layer-versions \
    --layer-name docerate-numpy-layer \
    --query 'LayerVersions[0].LayerVersionArn' --output text)

aws lambda update-function-configuration \
    --function-name docerate-rag-api \
    --layers $LAYER_ARN
```

### Step 7: Connect API Gateway to Lambda

```bash
# Get Lambda ARN
LAMBDA_ARN=$(aws lambda get-function \
    --function-name docerate-rag-api \
    --query 'Configuration.FunctionArn' --output text)

# Create Lambda integration
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
    --api-id $API_ID \
    --integration-type AWS_PROXY \
    --integration-uri $LAMBDA_ARN \
    --payload-format-version 2.0 \
    --query 'IntegrationId' --output text)

# Create catch-all route
aws apigatewayv2 create-route \
    --api-id $API_ID \
    --route-key 'ANY /{proxy+}' \
    --target integrations/$INTEGRATION_ID

# Create default stage
aws apigatewayv2 create-stage \
    --api-id $API_ID \
    --stage-name prod \
    --auto-deploy

# Grant API Gateway permission to invoke Lambda
aws lambda add-permission \
    --function-name docerate-rag-api \
    --statement-id apigateway-invoke \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:us-east-1:${ACCOUNT_ID}:${API_ID}/*"

# Get API endpoint
API_ENDPOINT="https://${API_ID}.execute-api.us-east-1.amazonaws.com/prod"
echo "API Endpoint: $API_ENDPOINT"
```

### Step 8: Build and Deploy Frontend

```bash
# Update frontend .env.production (use empty API_URL for relative URLs)
cat > rag-frontend/.env.production <<EOF
# API URL is empty - uses relative URLs routed through CloudFront
REACT_APP_API_URL=
REACT_APP_ENVIRONMENT=production
EOF

# Build frontend
cd rag-frontend
npm run build
cd ..

# Deploy to S3
FRONTEND_BUCKET=your-frontend-bucket \
CLOUDFRONT_DIST_ID=your-cloudfront-dist-id \
./scripts/deploy-frontend.sh
```

### Step 9: Create CloudFront Distribution with API Routing

**Important:** CloudFront now routes both frontend and API through a single domain (no CORS).

```bash
# Use the automated script to configure CloudFront with API routing
CLOUDFRONT_DIST_ID="your-distribution-id" \
API_GATEWAY_ID="your-api-id" \
./scripts/update-cloudfront-routing.sh

# Or create distribution manually and configure routing:
# See docs/CLOUDFRONT_API_ROUTING.md for detailed manual setup
```

The script will:
1. Add API Gateway as second origin
2. Create cache behavior for `/api/*` paths
3. Configure all HTTP methods (GET, POST, PUT, DELETE, etc.)
4. Set up same-origin routing (eliminates CORS)

**Note:** Distribution ID from output will be needed for frontend deployment.

### Step 10: Test Deployment

```bash
# Test API health
curl https://${API_ID}.execute-api.us-east-1.amazonaws.com/prod/health | jq

# Test tags endpoint
curl https://${API_ID}.execute-api.us-east-1.amazonaws.com/prod/api/tags | jq

# Test generate endpoint
curl -X POST https://${API_ID}.execute-api.us-east-1.amazonaws.com/prod/api/generate \
  -H "Content-Type: application/json" \
  -d '{"query":"","tags":["AI","SRE"]}' | jq

# Access frontend
echo "Frontend URL: https://your-cloudfront-domain.cloudfront.net"
```

---

## Configuration

### CloudFront API Routing (No CORS Needed!)

**Why No CORS:**
- Frontend and API share the same domain (CloudFront)
- Browser sees same-origin requests
- No CORS middleware needed in backend
- No CORS configuration needed in API Gateway

**CloudFront Configuration:**
- Two origins: S3 (frontend) + API Gateway (backend)
- Cache behavior routes `/api/*` to API Gateway origin
- Use `scripts/update-cloudfront-routing.sh` to configure automatically

**Frontend Configuration:**
```bash
# rag-frontend/.env.production
REACT_APP_API_URL=  # Empty = relative URLs = same-origin
```

**Local Development:**
```json
// rag-frontend/package.json
{
  "proxy": "http://localhost:5000"  // React dev server proxies API
}
```

**Backend - No CORS Middleware Needed:**
```python
# backend/main.py
# CORS middleware removed - not needed with CloudFront routing!
# Production: Same origin via CloudFront
# Local: Same origin via React dev server proxy
```

For detailed CloudFront setup, see: `docs/CLOUDFRONT_API_ROUTING.md`

### Lambda Configuration

**Memory and Timeout**:
```bash
aws lambda update-function-configuration \
    --function-name docerate-rag-api \
    --memory-size 512 \
    --timeout 30
```

**Environment Variables** (already set by deploy script):
- `ENVIRONMENT=production`
- `DATA_SOURCE=s3`
- `S3_BUCKET=your-rag-data-bucket`
- `LLM_PROVIDER=openrouter`
- `EMBEDDING_PROVIDER=bedrock`
- `OPENROUTER_API_KEY=your-key`

---

## Troubleshooting

### Issue: API Not Accessible Through CloudFront

**Symptom**: API calls to `https://cloudfront-domain.net/api/*` fail with 404 or 403

**Solution**:
1. Verify CloudFront has API Gateway origin configured:
   ```bash
   aws cloudfront get-distribution --id $CLOUDFRONT_DIST_ID \
     --query 'Distribution.DistributionConfig.Origins.Items[*].{Id: Id, Domain: DomainName}'
   ```
   Should show both S3 and API Gateway origins.

2. Verify `/api/*` cache behavior exists:
   ```bash
   aws cloudfront get-distribution --id $CLOUDFRONT_DIST_ID \
     --query 'Distribution.DistributionConfig.CacheBehaviors.Items[*].{PathPattern: PathPattern, TargetOriginId: TargetOriginId}'
   ```

3. Run the CloudFront routing script:
   ```bash
   ./scripts/update-cloudfront-routing.sh
   ```

4. Check CloudFront distribution status (must be "Deployed"):
   ```bash
   aws cloudfront get-distribution --id $CLOUDFRONT_DIST_ID \
     --query 'Distribution.Status'
   ```

### Issue: "Backend service is offline"

**Symptom**: Frontend shows API connection error

**Solutions**:
1. Verify frontend is using relative URLs (empty `REACT_APP_API_URL` in `.env.production`)
2. Test API through CloudFront:
   ```bash
   curl https://your-cloudfront-domain.net/api/health
   ```
3. Test API directly (should still work):
   ```bash
   curl https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/health
   ```
4. Verify Lambda function is deployed and active
5. Check Lambda CloudWatch logs for errors
6. Verify CloudFront cache behavior for `/api/*` is configured

### Issue: "Illegal header value b'Bearer'"

**Symptom**: OpenRouter API calls fail

**Solution**: This was fixed in the code. Ensure you're deploying with the OpenRouter API key:
```bash
OPENROUTER_API_KEY="your-actual-key" ./scripts/deploy-lambda.sh
```

### Issue: Lambda Cold Start Timeout

**Symptom**: First request takes >30s and times out

**Solutions**:
1. Increase Lambda timeout:
   ```bash
   aws lambda update-function-configuration \
       --function-name docerate-rag-api \
       --timeout 60
   ```

2. Keep Lambda warm with scheduled CloudWatch Events (optional)

3. Use Lambda provisioned concurrency (costs more)

### Issue: RAG Index Not Found

**Symptom**: Lambda logs show "Failed to load search index"

**Solutions**:
1. Verify S3 bucket has RAG data:
   ```bash
   aws s3 ls s3://your-rag-data-bucket/
   ```

2. Rebuild and redeploy index:
   ```bash
   ./scripts/index-unified.sh local --force
   S3_BUCKET=your-rag-data-bucket ./scripts/deploy-data.sh
   ```

3. Check Lambda has S3 read permissions

### Viewing Logs

```bash
# Lambda logs
aws logs tail /aws/lambda/docerate-rag-api --follow

# API Gateway logs (if enabled)
aws logs tail /aws/apigateway/docerate-rag-api --follow

# Filter for errors
aws logs tail /aws/lambda/docerate-rag-api --filter-pattern "ERROR"
```

---

## Updating the Deployment

### Update Backend Code

```bash
# Make code changes, then redeploy Lambda
LAMBDA_FUNCTION_NAME=docerate-rag-api \
LAMBDA_ROLE=$LAMBDA_ROLE \
S3_BUCKET=your-rag-data-bucket \
EMBEDDING_PROVIDER=bedrock \
EMBEDDING_MODEL=amazon.titan-embed-text-v2:0 \
BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0 \
LLM_PROVIDER=openrouter \
OPENROUTER_API_KEY="your-api-key" \
./scripts/deploy-lambda.sh
```

### Update Frontend

```bash
# Make frontend changes, rebuild and redeploy
cd rag-frontend
npm run build
cd ..
FRONTEND_BUCKET=your-frontend-bucket ./scripts/deploy-frontend.sh

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
    --distribution-id YOUR_DISTRIBUTION_ID \
    --paths "/*"
```

### Update RAG Index

```bash
# After adding new blog posts, rebuild index
./scripts/index-unified.sh local --force

# Deploy to S3
S3_BUCKET=your-rag-data-bucket ./scripts/deploy-data.sh

# Lambda will pick up new index on next cold start
# Or restart Lambda to force reload:
aws lambda update-function-configuration \
    --function-name docerate-rag-api \
    --environment Variables={FORCE_REFRESH="$(date +%s)"}
```

---

## Production Checklist

Before going live:

- [ ] **S3 Security (Origin Access Control)**
  - [ ] OAC configured: run `./scripts/setup-s3-oac.sh`
  - [ ] S3 bucket is private (not publicly accessible)
  - [ ] Block Public Access enabled (all 4 settings)
  - [ ] Direct S3 URLs return 403 Forbidden
  - [ ] CloudFront URL works (200 OK)
  - [ ] Custom error pages configured (403/404 → /index.html)
- [ ] **CloudFront API routing configured** (eliminates CORS)
  - [ ] Two origins: S3 (with OAC) + API Gateway
  - [ ] Cache behavior for `/api/*` paths
  - [ ] Frontend uses relative URLs (empty `REACT_APP_API_URL`)
  - [ ] S3 origin uses REST API endpoint (not website endpoint)
- [ ] Custom domain configured (Route 53 + CloudFront)
- [ ] SSL/TLS certificate added to CloudFront (ACM)
- [ ] CloudFront caching optimized (cache behaviors)
- [ ] Lambda provisioned concurrency enabled (if needed)
- [ ] CloudWatch alarms configured for errors
- [ ] API Gateway throttling configured
- [ ] IAM roles follow least privilege principle
- [ ] OpenRouter account has sufficient credits
- [ ] Bedrock model access enabled in AWS account
- [ ] Cost monitoring and budgets configured
- [ ] Backup strategy for S3 buckets (versioning)
- [ ] Verify no CORS errors in browser console (production test)
- [ ] Verify React SPA routing works (test deep links)

---

## Cost Optimization

### Estimated Monthly Costs (Light Usage)

- **Lambda**: $0-5 (first 1M requests free)
- **API Gateway**: $0-5 (first 1M requests free)
- **S3**: $1-3 (storage + requests)
- **CloudFront**: $1-5 (data transfer)
- **Bedrock**: ~$0.0001 per 1K tokens
- **OpenRouter**: Variable (depends on model and usage)

**Total**: ~$10-25/month for moderate traffic

### Tips to Reduce Costs

1. **Use CloudFront caching** aggressively for static content
2. **Optimize Lambda memory** (512MB is usually sufficient)
3. **Use S3 Intelligent-Tiering** for RAG data
4. **Enable API Gateway caching** (optional, costs extra)
5. **Monitor and optimize OpenRouter** usage
6. **Use cheaper LLM models** for non-critical generations

---

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use AWS Secrets Manager** for sensitive values (optional)
3. **✅ S3 Origin Access Control (OAC)** - S3 bucket is private, only accessible via CloudFront
   - Run `./scripts/setup-s3-oac.sh` to configure OAC security
   - See `docs/S3_SECURITY_OAC.md` for detailed guide
4. **Enable S3 Block Public Access** - all four settings enabled (configured by OAC setup)
5. **Enable S3 bucket encryption** at rest
6. **Use CloudFront signed URLs** for premium content (if needed)
7. **Implement API rate limiting** in API Gateway
8. **Enable AWS CloudTrail** for audit logging
9. **Regularly rotate** API keys and credentials
10. **Use IAM roles** instead of access keys where possible

---

## Support and Resources

- **AWS Documentation**: https://docs.aws.amazon.com/
- **FastAPI on Lambda**: https://github.com/jordaneremieff/mangum
- **OpenRouter Docs**: https://openrouter.ai/docs
- **Bedrock Docs**: https://docs.aws.amazon.com/bedrock/
- **CloudFront API Routing**: See `docs/CLOUDFRONT_API_ROUTING.md` for detailed setup

For issues with this deployment, check CloudWatch logs first, then review the troubleshooting section above.

---

## Recent Architecture Changes

### S3 Origin Access Control (Security Enhancement)

As of October 2024, S3 security has been hardened with Origin Access Control (OAC):

**Before (Insecure):**
- S3 bucket was publicly accessible
- Anyone could bypass CloudFront and access S3 directly
- Security gap: no access control or logging for direct S3 access

**After (Secure):**
- S3 bucket is **completely private**
- Only CloudFront can access S3 via OAC signatures (AWS Signature v4)
- S3 Block Public Access enabled (all 4 settings)
- Direct S3 URLs return 403 Forbidden

**Benefits:**
- ✅ Zero-trust S3 access (CloudFront-only)
- ✅ Prevents bandwidth theft and unauthorized access
- ✅ Defense in depth (S3 blocks access even if CloudFront misconfigured)
- ✅ Foundation for future WAF rules and security controls
- ✅ Deployment workflows unchanged (AWS CLI uses IAM credentials)

**Configuration:**
```bash
# Automated setup script handles all OAC configuration
./scripts/setup-s3-oac.sh
```

**Verification:**
```bash
# CloudFront URL works (200 OK)
curl -I https://d2w8hymo03zbys.cloudfront.net

# Direct S3 URL blocked (403 Forbidden)
curl -I https://docerate-frontend.s3.amazonaws.com/index.html
```

See `docs/S3_SECURITY_OAC.md` for complete details and technical architecture.

### CloudFront API Routing (Eliminates CORS)

As of October 2024, the architecture has been updated to route API requests through CloudFront:

**Before:**
- Frontend: CloudFront → S3
- API: Direct to API Gateway (different domain)
- Required CORS middleware in backend

**After:**
- Frontend: CloudFront → /* → S3 (secured with OAC)
- API: CloudFront → /api/* → API Gateway
- Same domain = No CORS needed!

**Benefits:**
- ✅ Simpler backend code (no CORS middleware)
- ✅ Better security (single entry point)
- ✅ Consistent architecture (prod + local dev)
- ✅ Optional edge caching for API responses

See `docs/CLOUDFRONT_API_ROUTING.md` for complete details and migration guide.
