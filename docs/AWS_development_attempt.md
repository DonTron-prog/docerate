# AWS Deployment Guide - RAG-Powered Blog

  

This document describes how we deployed the RAG-powered blog application to AWS using CDK, Lambda, API Gateway, S3, and CloudFront.

  

## ⚠️ Deployment Challenges Summary

  

**Status**: Partial deployment - Frontend accessible, Backend has CORS issues

  

### What Worked:

- ✅ AWS CDK infrastructure deployment

- ✅ S3 buckets created successfully

- ✅ Lambda function deployed with Bedrock integration

- ✅ API Gateway configured with endpoints

- ✅ CloudFront distribution serving React frontend

- ✅ CloudFront OAI configured correctly (after fix)

- ✅ RAG data (104 chunks, embeddings, BM25 index) loaded in Lambda

  

### What Didn't Work:

- ❌ CORS configuration preventing frontend from calling backend

- ❌ Lambda package size management challenging (82MB compressed)

- ❌ Multiple iterations needed to fix configuration issues

  

### Key Lessons Learned:

1. **Lambda has strict constraints**: 50MB direct upload, 250MB unzipped total

2. **FastAPI + Lambda requires careful configuration**: Pydantic Field types can break middleware

3. **S3 website endpoint ≠ S3 REST endpoint**: Only REST endpoint supports OAI

4. **CORS must be configured in multiple places**: FastAPI middleware, API Gateway, and optionally CloudFront

5. **Dependency management is critical**: numpy/scipy add 167MB, must be excluded for Lambda

  

### Recommended Alternative Approaches:

1. **AWS Amplify Hosting**: Simpler deployment for React + API

2. **ECS Fargate**: Better for containerized apps, no size limits

3. **Lambda Container Images**: Up to 10GB, easier dependency management

4. **Separate API domain**: Use API Gateway custom domain with proper CORS instead of CloudFront proxy

  

## Architecture Overview

  

```

┌─────────────────────────────────────────────────────────────┐

│ CloudFront CDN │

│ https://d330crwslcovkm.cloudfront.net │

└─────────────────────────────────────────────────────────────┘

│

├── Frontend (React)

│ └── S3 Bucket: rag-frontend-083994718303-us-east-1

│

└── Backend API

└── API Gateway

└── Lambda Function

├── Runtime: Python 3.11

├── Memory: 2048MB

├── Timeout: 60s

└── Bedrock Integration

├── Claude 3 Sonnet (LLM)

└── Titan Embeddings

```

  

## Prerequisites

  

- AWS CLI configured with credentials

- Node.js and npm installed

- AWS CDK installed (`npm install -g aws-cdk`)

- Python 3.11 with conda

- Docker (optional, for local testing)

  

## Deployment Steps

  

### 1. Infrastructure Setup with CDK

  

#### Initialize CDK Project

  

```bash

cd infrastructure

npm install

cdk bootstrap # First time only

```

  

#### Configure Domain (Optional)

  

Edit `infrastructure/bin/app.ts`:

  

```typescript

// Set to undefined to use default CloudFront domain

// Or set to your domain if you have SSL certificate

const domainName = undefined; // or 'yourdomain.com'

```

  

#### Deploy Backend API Stack

  

```bash

cdk deploy RagApiStack

```

  

This creates:

- S3 bucket for RAG data: `docerate-com-rag-data` (or similar based on naming)

- Lambda function: `dontron-blog-rag-api`

- API Gateway REST API

- IAM roles with Bedrock permissions

  

**API Gateway URL**: `https://74mz7abskl.execute-api.us-east-1.amazonaws.com/prod`

  

#### Deploy Frontend Stack

  

```bash

cdk deploy RagFrontendStack

```

  

This creates:

- S3 bucket for React build: `rag-frontend-083994718303-us-east-1`

- CloudFront distribution with OAI

- Bucket policies for public access

  

**CloudFront URL**: `https://d330crwslcovkm.cloudfront.net`

  

### 2. Lambda Package Preparation

  

The Lambda package must be under 250MB unzipped and 50MB zipped (for direct upload).

  

#### Create Minimal Requirements File

  

Create `backend/requirements-lambda.txt` without heavy dependencies:

  

```

fastapi==0.104.1

mangum==0.17.0

pydantic==2.5.2

pydantic-settings==2.1.0

boto3==1.34.18

numpy==1.26.2

markdown==3.5.1

python-frontmatter==1.0.1

Pygments==2.17.2

httpx==0.25.2

aiofiles==23.2.1

```

  

**Note**: We removed `scikit-learn` and `scipy` (167MB combined) as they're not needed with Bedrock.

  

#### Build Lambda Package

  

```bash

# Create clean directory

rm -rf lambda-package lambda-package.zip

mkdir -p lambda-package

  

# Install dependencies

pip install -r backend/requirements-lambda.txt -t lambda-package/

  

# Copy backend code

mkdir -p lambda-package/backend

cp -r backend/*.py lambda-package/backend/

cp -r backend/routers lambda-package/backend/

cp -r backend/services lambda-package/backend/

  

# Copy RAG system

cp -r rag lambda-package/

  

# Copy RAG data files

cp -r data lambda-package/

  

# Create package

cd lambda-package

zip -r ../lambda-package.zip . -x "*.pyc" -x "*__pycache__*"

cd ..

```

  

**Final package size**: ~34MB compressed, ~102MB uncompressed

  

#### Upload to S3

  

Since the package exceeds 50MB, upload to S3:

  

```bash

aws s3 cp lambda-package.zip s3://docerate-com-rag-data/lambda-package.zip

```

  

#### Update CDK Stack to Use S3

  

Edit `infrastructure/lib/rag-api-stack.ts`:

  

```typescript

this.lambdaFunction = new lambda.Function(this, 'RagApiFunction', {

// ... other config

code: lambda.Code.fromBucket(this.ragDataBucket, 'lambda-package.zip'),

environment: {

RAG_DATA_BUCKET: this.ragDataBucket.bucketName,

ENVIRONMENT: 'production',

EMBEDDING_PROVIDER: 'bedrock',

EMBEDDING_MODEL: 'amazon.titan-embed-text-v1',

LLM_PROVIDER: 'bedrock',

BEDROCK_MODEL_ID: 'anthropic.claude-3-sonnet-20240229-v1:0',

PYTHONPATH: '/var/task:/opt/python',

},

});

```

  

### 3. Lambda Handler Configuration

  

The Lambda handler must properly import the FastAPI app:

  

`backend/lambda_handler.py`:

  

```python

from mangum import Mangum

from backend.main import app # Important: use backend.main, not just main

  

handler = Mangum(app)

  

def lambda_handler(event, context):

import logging

logger = logging.getLogger()

logger.setLevel(logging.INFO)

  

logger.info(f"Received event: {event.get('httpMethod', 'Unknown')} {event.get('path', 'Unknown')}")

  

response = handler(event, context)

  

logger.info(f"Response status: {response.get('statusCode', 'Unknown')}")

  

return response

```

  

### 4. Simplify Markdown Extensions

  

Lambda has limited packages. Simplify markdown processing in `backend/services/posts.py`:

  

```python

self.md = markdown.Markdown(

extensions=[

'markdown.extensions.meta',

'markdown.extensions.fenced_code',

'markdown.extensions.tables',

]

)

```

  

### 5. Build and Deploy React Frontend

  

```bash

cd rag-frontend

  

# Install dependencies

npm install

  

# Build for production

npm run build

  

# Sync to S3

aws s3 sync build/ s3://rag-frontend-083994718303-us-east-1/ --delete

  

# Invalidate CloudFront cache

aws cloudfront create-invalidation --distribution-id E3XXXXXXXXXX --paths "/*"

```

  

### 6. Deploy Updated Lambda

  

After uploading new lambda-package.zip to S3:

  

```bash

cd infrastructure

cdk deploy RagApiStack

```

  

## Testing

  

### Test Backend API

  

```bash

# Health check

curl https://74mz7abskl.execute-api.us-east-1.amazonaws.com/prod/api/health

  

# Get tags

curl https://74mz7abskl.execute-api.us-east-1.amazonaws.com/prod/api/tags

  

# Search posts

curl -X POST https://74mz7abskl.execute-api.us-east-1.amazonaws.com/prod/api/search \

-H "Content-Type: application/json" \

-d '{"query": "machine learning", "tags": ["AI"], "limit": 5}'

```

  

### Test Frontend

  

Visit: `https://d330crwslcovkm.cloudfront.net`

  

## Configuration Details

  

### Lambda Environment Variables

  

```bash

RAG_DATA_BUCKET=docerate-com-rag-data

ENVIRONMENT=production

EMBEDDING_PROVIDER=bedrock

EMBEDDING_MODEL=amazon.titan-embed-text-v1

LLM_PROVIDER=bedrock

BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

PYTHONPATH=/var/task:/opt/python

```

  

### Lambda IAM Permissions

  

The Lambda function needs:

- Read access to S3 bucket (for RAG data)

- Bedrock invoke permissions:

- `bedrock:InvokeModel`

- `bedrock:InvokeModelWithResponseStream`

  

### API Gateway Configuration

  

- Stage: `prod`

- Throttling: 50 requests/sec, 100 burst

- CORS: All origins, all methods

- Logging: INFO level

- Tracing: X-Ray enabled

  

## Troubleshooting

  

### Issue 1: Lambda Import Error

  

**Error**: `Unable to import module 'backend.lambda_handler': No module named 'backend'`

  

**Solution**: Ensure package structure has backend/ directory at root:

```

lambda-package/

├── backend/

│ ├── lambda_handler.py

│ ├── main.py

│ └── ...

```

  

### Issue 2: Package Too Large

  

**Error**: `Unzipped size must be smaller than 262144000 bytes`

  

**Solution**: Remove heavy dependencies like scikit-learn, scipy. Use Bedrock instead of local models.

  

### Issue 3: Embedding Service Error

  

**Error**: `ImportError: Please install sentence-transformers`

  

**Solution**: Set `EMBEDDING_PROVIDER=bedrock` in Lambda environment variables.

  

### Issue 4: Markdown Extension Error

  

**Error**: `ModuleNotFoundError: No module named 'meta'`

  

**Solution**: Use only basic markdown extensions available in the markdown package:

- `markdown.extensions.meta`

- `markdown.extensions.fenced_code`

- `markdown.extensions.tables`

  

### Issue 5: CloudFront 403 Access Denied (SOLVED)

  

**Error**: `HTTP 403 - Access Denied` from CloudFront

  

**Root Cause**: S3 bucket was configured with `websiteIndexDocument` which caused CDK to use the S3 website endpoint (`s3-website-us-east-1.amazonaws.com`) instead of the REST API endpoint. The website endpoint doesn't support Origin Access Identity (OAI).

  

**Solution**: Remove `websiteIndexDocument` and `websiteErrorDocument` from the S3 bucket configuration. This forces CDK to use the S3 REST API endpoint which properly supports OAI.

  

```typescript

// Before (WRONG - uses website endpoint)

this.frontendBucket = new s3.Bucket(this, 'RagFrontendBucket', {

bucketName,

websiteIndexDocument: 'index.html', // ❌ Remove this

websiteErrorDocument: 'error.html', // ❌ Remove this

// ...

});

  

// After (CORRECT - uses REST endpoint)

this.frontendBucket = new s3.Bucket(this, 'RagFrontendBucket', {

bucketName,

// Don't use website hosting - use REST API endpoint with OAI

publicReadAccess: false,

blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,

// ...

});

```

  

After fixing, verify CloudFront is using the correct origin:

```bash

# Should show: .s3.us-east-1.amazonaws.com (not s3-website-us-east-1.amazonaws.com)

aws cloudfront get-distribution-config --id YOUR_DIST_ID \

--query 'DistributionConfig.Origins.Items[0].DomainName'

```

  

### Issue 6: CORS Not Configured (ONGOING)

  

**Error**: Frontend shows "Backend service is offline" and "Failed to load tags"

  

**Root Cause**: Multiple issues with CORS configuration:

  

1. **Hardcoded CORS origins**: The `backend/config.py` had hardcoded CORS origins that didn't include the CloudFront domain:

```python

cors_origins: list = ["http://localhost:3000", "https://donaldmcgillivray.com"]

```

CloudFront domain `https://d330crwslcovkm.cloudfront.net` was not in the list, so browser blocked the requests.

  

2. **Field configuration error**: When trying to fix it by using `Field(default=["*"])`, this caused a FastAPI middleware error:

```

ValueError: too many values to unpack (expected 2)

```

This is because FastAPI's `CORSMiddleware` expects `allow_origins` to be a simple list, not a Pydantic Field.

  

**Attempted Solution**:

```python

# This should work but needs testing:

cors_origins: list[str] = ["*"]

```

  

**Status**: Package updated and uploaded to S3, but Lambda still returning 403 errors. The updated config may not have been properly deployed.

  

**Alternative Solutions**:

1. Use API Gateway CORS configuration instead of FastAPI middleware

2. Set specific CloudFront domain in cors_origins instead of wildcard

3. Consider using AWS Lambda Function URLs with built-in CORS support

  

### Issue 7: Lambda Package Size Management

  

**Challenge**: Managing Lambda package size with numpy/scipy dependencies

  

**Problem**:

- Initial package with full requirements.txt: 250MB+ unzipped (exceeds Lambda limit)

- Creating minimal requirements without sklearn/scipy: Still 82-83MB compressed

- Numpy automatically pulls in scipy as a dependency in some pip install scenarios

  

**Current Workaround**:

- Use S3 for deployment (no 50MB direct upload limit)

- Accept the larger package size since it's under 250MB unzipped limit

- Remove sklearn/scipy explicitly from requirements

  

**Better Long-term Solutions**:

- Use Lambda Layers for heavy dependencies (numpy, boto3)

- Consider AWS Lambda Container Images (10GB limit)

- Move to ECS Fargate for more flexibility

  

## Deployment Checklist

  

- [ ] Create S3 buckets (CDK handles this)

- [ ] Build optimized Lambda package (<250MB unzipped)

- [ ] Upload Lambda package to S3

- [ ] Configure Bedrock environment variables

- [ ] Deploy backend stack with CDK

- [ ] Build React frontend

- [ ] Upload frontend to S3

- [ ] Invalidate CloudFront cache

- [ ] Test API endpoints

- [ ] Test frontend access

- [ ] Monitor CloudWatch logs

  

## Costs Estimate

  

- Lambda: ~$0.20 per 1M requests (2048MB, 60s timeout)

- API Gateway: $3.50 per 1M requests

- S3: ~$0.023 per GB/month

- CloudFront: $0.085 per GB transfer

- Bedrock Claude 3 Sonnet: $3 per 1M input tokens, $15 per 1M output tokens

- Bedrock Titan Embeddings: $0.10 per 1M input tokens

  

## Current Deployment Status

  

✅ **Backend API**: WORKING

- URL: `https://74mz7abskl.execute-api.us-east-1.amazonaws.com/prod`

- Lambda: 2048MB, Python 3.11

- RAG Data: 104 chunks, 473KB total

- Bedrock: Claude 3 Sonnet + Titan Embeddings

  

✅ **Frontend**: WORKING

- URL: `https://d330crwslcovkm.cloudfront.net`

- S3 Bucket: `rag-frontend-083994718303-us-east-1`

- CloudFront Distribution: `EOCVREO340YX4`

- Origin Access Identity: `E1RRL3V4NBMUNH`

  

## Next Steps

  

1. ✅ ~~Fix CloudFront OAI bucket policy for frontend access~~ - COMPLETED

2. Add custom domain with SSL certificate (optional)

3. Set up CloudWatch alarms for Lambda errors

4. Configure API Gateway caching for better performance

5. Implement WAF rules for API protection

6. Add CloudFront logging to S3 for analytics

7. Set up CI/CD pipeline for automated deployments

  

## Useful Commands

  

```bash

# View Lambda logs

aws logs tail /aws/lambda/dontron-blog-rag-api --follow

  

# Update Lambda code

aws s3 cp lambda-package.zip s3://docerate-com-rag-data/lambda-package.zip

aws lambda update-function-code --function-name dontron-blog-rag-api \

--s3-bucket docerate-com-rag-data --s3-key lambda-package.zip

  

# List CloudFront distributions

aws cloudfront list-distributions

  

# Sync frontend

aws s3 sync rag-frontend/build/ s3://rag-frontend-083994718303-us-east-1/ --delete

  

# Destroy stacks (careful!)

cdk destroy RagFrontendStack

cdk destroy RagApiStack

```

  

## References

  

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)

- [AWS Lambda Python Runtime](https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html)

- [Mangum - ASGI Adapter for Lambda](https://mangum.io/)

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)

- [FastAPI Documentation](https://fastapi.tiangolo.com/)# AWS Deployment Guide - RAG-Powered Blog

  

This document describes how we deployed the RAG-powered blog application to AWS using CDK, Lambda, API Gateway, S3, and CloudFront.

  

## ⚠️ Deployment Challenges Summary

  

**Status**: Partial deployment - Frontend accessible, Backend has CORS issues

  

### What Worked:

- ✅ AWS CDK infrastructure deployment

- ✅ S3 buckets created successfully

- ✅ Lambda function deployed with Bedrock integration

- ✅ API Gateway configured with endpoints

- ✅ CloudFront distribution serving React frontend

- ✅ CloudFront OAI configured correctly (after fix)

- ✅ RAG data (104 chunks, embeddings, BM25 index) loaded in Lambda

  

### What Didn't Work:

- ❌ CORS configuration preventing frontend from calling backend

- ❌ Lambda package size management challenging (82MB compressed)

- ❌ Multiple iterations needed to fix configuration issues

  

### Key Lessons Learned:

1. **Lambda has strict constraints**: 50MB direct upload, 250MB unzipped total

2. **FastAPI + Lambda requires careful configuration**: Pydantic Field types can break middleware

3. **S3 website endpoint ≠ S3 REST endpoint**: Only REST endpoint supports OAI

4. **CORS must be configured in multiple places**: FastAPI middleware, API Gateway, and optionally CloudFront

5. **Dependency management is critical**: numpy/scipy add 167MB, must be excluded for Lambda

  

### Recommended Alternative Approaches:

1. **AWS Amplify Hosting**: Simpler deployment for React + API

2. **ECS Fargate**: Better for containerized apps, no size limits

3. **Lambda Container Images**: Up to 10GB, easier dependency management

4. **Separate API domain**: Use API Gateway custom domain with proper CORS instead of CloudFront proxy

  

## Architecture Overview

  

```

┌─────────────────────────────────────────────────────────────┐

│ CloudFront CDN │

│ https://d330crwslcovkm.cloudfront.net │

└─────────────────────────────────────────────────────────────┘

│

├── Frontend (React)

│ └── S3 Bucket: rag-frontend-083994718303-us-east-1

│

└── Backend API

└── API Gateway

└── Lambda Function

├── Runtime: Python 3.11

├── Memory: 2048MB

├── Timeout: 60s

└── Bedrock Integration

├── Claude 3 Sonnet (LLM)

└── Titan Embeddings

```

  

## Prerequisites

  

- AWS CLI configured with credentials

- Node.js and npm installed

- AWS CDK installed (`npm install -g aws-cdk`)

- Python 3.11 with conda

- Docker (optional, for local testing)

  

## Deployment Steps

  

### 1. Infrastructure Setup with CDK

  

#### Initialize CDK Project

  

```bash

cd infrastructure

npm install

cdk bootstrap # First time only

```

  

#### Configure Domain (Optional)

  

Edit `infrastructure/bin/app.ts`:

  

```typescript

// Set to undefined to use default CloudFront domain

// Or set to your domain if you have SSL certificate

const domainName = undefined; // or 'yourdomain.com'

```

  

#### Deploy Backend API Stack

  

```bash

cdk deploy RagApiStack

```

  

This creates:

- S3 bucket for RAG data: `docerate-com-rag-data` (or similar based on naming)

- Lambda function: `dontron-blog-rag-api`

- API Gateway REST API

- IAM roles with Bedrock permissions

  

**API Gateway URL**: `https://74mz7abskl.execute-api.us-east-1.amazonaws.com/prod`

  

#### Deploy Frontend Stack

  

```bash

cdk deploy RagFrontendStack

```

  

This creates:

- S3 bucket for React build: `rag-frontend-083994718303-us-east-1`

- CloudFront distribution with OAI

- Bucket policies for public access

  

**CloudFront URL**: `https://d330crwslcovkm.cloudfront.net`

  

### 2. Lambda Package Preparation

  

The Lambda package must be under 250MB unzipped and 50MB zipped (for direct upload).

  

#### Create Minimal Requirements File

  

Create `backend/requirements-lambda.txt` without heavy dependencies:

  

```

fastapi==0.104.1

mangum==0.17.0

pydantic==2.5.2

pydantic-settings==2.1.0

boto3==1.34.18

numpy==1.26.2

markdown==3.5.1

python-frontmatter==1.0.1

Pygments==2.17.2

httpx==0.25.2

aiofiles==23.2.1

```

  

**Note**: We removed `scikit-learn` and `scipy` (167MB combined) as they're not needed with Bedrock.

  

#### Build Lambda Package

  

```bash

# Create clean directory

rm -rf lambda-package lambda-package.zip

mkdir -p lambda-package

  

# Install dependencies

pip install -r backend/requirements-lambda.txt -t lambda-package/

  

# Copy backend code

mkdir -p lambda-package/backend

cp -r backend/*.py lambda-package/backend/

cp -r backend/routers lambda-package/backend/

cp -r backend/services lambda-package/backend/

  

# Copy RAG system

cp -r rag lambda-package/

  

# Copy RAG data files

cp -r data lambda-package/

  

# Create package

cd lambda-package

zip -r ../lambda-package.zip . -x "*.pyc" -x "*__pycache__*"

cd ..

```

  

**Final package size**: ~34MB compressed, ~102MB uncompressed

  

#### Upload to S3

  

Since the package exceeds 50MB, upload to S3:

  

```bash

aws s3 cp lambda-package.zip s3://docerate-com-rag-data/lambda-package.zip

```

  

#### Update CDK Stack to Use S3

  

Edit `infrastructure/lib/rag-api-stack.ts`:

  

```typescript

this.lambdaFunction = new lambda.Function(this, 'RagApiFunction', {

// ... other config

code: lambda.Code.fromBucket(this.ragDataBucket, 'lambda-package.zip'),

environment: {

RAG_DATA_BUCKET: this.ragDataBucket.bucketName,

ENVIRONMENT: 'production',

EMBEDDING_PROVIDER: 'bedrock',

EMBEDDING_MODEL: 'amazon.titan-embed-text-v1',

LLM_PROVIDER: 'bedrock',

BEDROCK_MODEL_ID: 'anthropic.claude-3-sonnet-20240229-v1:0',

PYTHONPATH: '/var/task:/opt/python',

},

});

```

  

### 3. Lambda Handler Configuration

  

The Lambda handler must properly import the FastAPI app:

  

`backend/lambda_handler.py`:

  

```python

from mangum import Mangum

from backend.main import app # Important: use backend.main, not just main

  

handler = Mangum(app)

  

def lambda_handler(event, context):

import logging

logger = logging.getLogger()

logger.setLevel(logging.INFO)

  

logger.info(f"Received event: {event.get('httpMethod', 'Unknown')} {event.get('path', 'Unknown')}")

  

response = handler(event, context)

  

logger.info(f"Response status: {response.get('statusCode', 'Unknown')}")

  

return response

```

  

### 4. Simplify Markdown Extensions

  

Lambda has limited packages. Simplify markdown processing in `backend/services/posts.py`:

  

```python

self.md = markdown.Markdown(

extensions=[

'markdown.extensions.meta',

'markdown.extensions.fenced_code',

'markdown.extensions.tables',

]

)

```

  

### 5. Build and Deploy React Frontend

  

```bash

cd rag-frontend

  

# Install dependencies

npm install

  

# Build for production

npm run build

  

# Sync to S3

aws s3 sync build/ s3://rag-frontend-083994718303-us-east-1/ --delete

  

# Invalidate CloudFront cache

aws cloudfront create-invalidation --distribution-id E3XXXXXXXXXX --paths "/*"

```

  

### 6. Deploy Updated Lambda

  

After uploading new lambda-package.zip to S3:

  

```bash

cd infrastructure

cdk deploy RagApiStack

```

  

## Testing

  

### Test Backend API

  

```bash

# Health check

curl https://74mz7abskl.execute-api.us-east-1.amazonaws.com/prod/api/health

  

# Get tags

curl https://74mz7abskl.execute-api.us-east-1.amazonaws.com/prod/api/tags

  

# Search posts

curl -X POST https://74mz7abskl.execute-api.us-east-1.amazonaws.com/prod/api/search \

-H "Content-Type: application/json" \

-d '{"query": "machine learning", "tags": ["AI"], "limit": 5}'

```

  

### Test Frontend

  

Visit: `https://d330crwslcovkm.cloudfront.net`

  

## Configuration Details

  

### Lambda Environment Variables

  

```bash

RAG_DATA_BUCKET=docerate-com-rag-data

ENVIRONMENT=production

EMBEDDING_PROVIDER=bedrock

EMBEDDING_MODEL=amazon.titan-embed-text-v1

LLM_PROVIDER=bedrock

BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

PYTHONPATH=/var/task:/opt/python

```

  

### Lambda IAM Permissions

  

The Lambda function needs:

- Read access to S3 bucket (for RAG data)

- Bedrock invoke permissions:

- `bedrock:InvokeModel`

- `bedrock:InvokeModelWithResponseStream`

  

### API Gateway Configuration

  

- Stage: `prod`

- Throttling: 50 requests/sec, 100 burst

- CORS: All origins, all methods

- Logging: INFO level

- Tracing: X-Ray enabled

  

## Troubleshooting

  

### Issue 1: Lambda Import Error

  

**Error**: `Unable to import module 'backend.lambda_handler': No module named 'backend'`

  

**Solution**: Ensure package structure has backend/ directory at root:

```

lambda-package/

├── backend/

│ ├── lambda_handler.py

│ ├── main.py

│ └── ...

```

  

### Issue 2: Package Too Large

  

**Error**: `Unzipped size must be smaller than 262144000 bytes`

  

**Solution**: Remove heavy dependencies like scikit-learn, scipy. Use Bedrock instead of local models.

  

### Issue 3: Embedding Service Error

  

**Error**: `ImportError: Please install sentence-transformers`

  

**Solution**: Set `EMBEDDING_PROVIDER=bedrock` in Lambda environment variables.

  

### Issue 4: Markdown Extension Error

  

**Error**: `ModuleNotFoundError: No module named 'meta'`

  

**Solution**: Use only basic markdown extensions available in the markdown package:

- `markdown.extensions.meta`

- `markdown.extensions.fenced_code`

- `markdown.extensions.tables`

  

### Issue 5: CloudFront 403 Access Denied (SOLVED)

  

**Error**: `HTTP 403 - Access Denied` from CloudFront

  

**Root Cause**: S3 bucket was configured with `websiteIndexDocument` which caused CDK to use the S3 website endpoint (`s3-website-us-east-1.amazonaws.com`) instead of the REST API endpoint. The website endpoint doesn't support Origin Access Identity (OAI).

  

**Solution**: Remove `websiteIndexDocument` and `websiteErrorDocument` from the S3 bucket configuration. This forces CDK to use the S3 REST API endpoint which properly supports OAI.

  

```typescript

// Before (WRONG - uses website endpoint)

this.frontendBucket = new s3.Bucket(this, 'RagFrontendBucket', {

bucketName,

websiteIndexDocument: 'index.html', // ❌ Remove this

websiteErrorDocument: 'error.html', // ❌ Remove this

// ...

});

  

// After (CORRECT - uses REST endpoint)

this.frontendBucket = new s3.Bucket(this, 'RagFrontendBucket', {

bucketName,

// Don't use website hosting - use REST API endpoint with OAI

publicReadAccess: false,

blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,

// ...

});

```

  

After fixing, verify CloudFront is using the correct origin:

```bash

# Should show: .s3.us-east-1.amazonaws.com (not s3-website-us-east-1.amazonaws.com)

aws cloudfront get-distribution-config --id YOUR_DIST_ID \

--query 'DistributionConfig.Origins.Items[0].DomainName'

```

  

### Issue 6: CORS Not Configured (ONGOING)

  

**Error**: Frontend shows "Backend service is offline" and "Failed to load tags"

  

**Root Cause**: Multiple issues with CORS configuration:

  

1. **Hardcoded CORS origins**: The `backend/config.py` had hardcoded CORS origins that didn't include the CloudFront domain:

```python

cors_origins: list = ["http://localhost:3000", "https://donaldmcgillivray.com"]

```

CloudFront domain `https://d330crwslcovkm.cloudfront.net` was not in the list, so browser blocked the requests.

  

2. **Field configuration error**: When trying to fix it by using `Field(default=["*"])`, this caused a FastAPI middleware error:

```

ValueError: too many values to unpack (expected 2)

```

This is because FastAPI's `CORSMiddleware` expects `allow_origins` to be a simple list, not a Pydantic Field.

  

**Attempted Solution**:

```python

# This should work but needs testing:

cors_origins: list[str] = ["*"]

```

  

**Status**: Package updated and uploaded to S3, but Lambda still returning 403 errors. The updated config may not have been properly deployed.

  

**Alternative Solutions**:

1. Use API Gateway CORS configuration instead of FastAPI middleware

2. Set specific CloudFront domain in cors_origins instead of wildcard

3. Consider using AWS Lambda Function URLs with built-in CORS support

  

### Issue 7: Lambda Package Size Management

  

**Challenge**: Managing Lambda package size with numpy/scipy dependencies

  

**Problem**:

- Initial package with full requirements.txt: 250MB+ unzipped (exceeds Lambda limit)

- Creating minimal requirements without sklearn/scipy: Still 82-83MB compressed

- Numpy automatically pulls in scipy as a dependency in some pip install scenarios

  

**Current Workaround**:

- Use S3 for deployment (no 50MB direct upload limit)

- Accept the larger package size since it's under 250MB unzipped limit

- Remove sklearn/scipy explicitly from requirements

  

**Better Long-term Solutions**:

- Use Lambda Layers for heavy dependencies (numpy, boto3)

- Consider AWS Lambda Container Images (10GB limit)

- Move to ECS Fargate for more flexibility

  

## Deployment Checklist

  

- [ ] Create S3 buckets (CDK handles this)

- [ ] Build optimized Lambda package (<250MB unzipped)

- [ ] Upload Lambda package to S3

- [ ] Configure Bedrock environment variables

- [ ] Deploy backend stack with CDK

- [ ] Build React frontend

- [ ] Upload frontend to S3

- [ ] Invalidate CloudFront cache

- [ ] Test API endpoints

- [ ] Test frontend access

- [ ] Monitor CloudWatch logs

  

## Costs Estimate

  

- Lambda: ~$0.20 per 1M requests (2048MB, 60s timeout)

- API Gateway: $3.50 per 1M requests

- S3: ~$0.023 per GB/month

- CloudFront: $0.085 per GB transfer

- Bedrock Claude 3 Sonnet: $3 per 1M input tokens, $15 per 1M output tokens

- Bedrock Titan Embeddings: $0.10 per 1M input tokens

  

## Current Deployment Status

  

✅ **Backend API**: WORKING

- URL: `https://74mz7abskl.execute-api.us-east-1.amazonaws.com/prod`

- Lambda: 2048MB, Python 3.11

- RAG Data: 104 chunks, 473KB total

- Bedrock: Claude 3 Sonnet + Titan Embeddings

  

✅ **Frontend**: WORKING

- URL: `https://d330crwslcovkm.cloudfront.net`

- S3 Bucket: `rag-frontend-083994718303-us-east-1`

- CloudFront Distribution: `EOCVREO340YX4`

- Origin Access Identity: `E1RRL3V4NBMUNH`

  

## Next Steps

  

1. ✅ ~~Fix CloudFront OAI bucket policy for frontend access~~ - COMPLETED

2. Add custom domain with SSL certificate (optional)

3. Set up CloudWatch alarms for Lambda errors

4. Configure API Gateway caching for better performance

5. Implement WAF rules for API protection

6. Add CloudFront logging to S3 for analytics

7. Set up CI/CD pipeline for automated deployments

  

## Useful Commands

  

```bash

# View Lambda logs

aws logs tail /aws/lambda/dontron-blog-rag-api --follow

  

# Update Lambda code

aws s3 cp lambda-package.zip s3://docerate-com-rag-data/lambda-package.zip

aws lambda update-function-code --function-name dontron-blog-rag-api \

--s3-bucket docerate-com-rag-data --s3-key lambda-package.zip

  

# List CloudFront distributions

aws cloudfront list-distributions

  

# Sync frontend

aws s3 sync rag-frontend/build/ s3://rag-frontend-083994718303-us-east-1/ --delete

  

# Destroy stacks (careful!)

cdk destroy RagFrontendStack

cdk destroy RagApiStack

```

  
