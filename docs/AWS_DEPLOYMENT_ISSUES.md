# AWS Deployment Issues Documentation

## Overview
This document outlines all the issues encountered while deploying the RAG-powered blog system to AWS using Lambda, API Gateway, S3, and CloudFront.

## Architecture Components
- **Lambda Function**: docerate-rag-api (FastAPI backend)
- **API Gateway**: HTTP API with /prod stage
- **S3 Buckets**:
  - docerate-rag-data (vector embeddings and search index)
  - docerate-frontend (React static site)
- **CloudFront**: CDN distribution for docerate.com
- **Route 53**: DNS management

## Issues Encountered and Resolutions

### 1. Lambda Package Size Constraints
**Issue**: Initial Lambda deployment package was 1.8GB, exceeding the 250MB limit.
- Caused by PyTorch and sentence-transformers dependencies

**Resolution**:
- Removed PyTorch/sentence-transformers from Lambda requirements
- Pre-generate embeddings locally and upload to S3
- Created Lambda layer for NumPy dependency
- Final package size: ~26MB

### 2. Import Path Issues
**Issue**: Lambda handler failed with "No module named 'backend'"
```python
# Failed:
from backend.main import app

# Fixed:
from main import app
```

**Resolution**: Removed `backend.` prefix from all imports in Lambda package

### 3. Missing Dependencies
**Issue**: Lambda missing required packages
- markdown
- python-frontmatter
- rag module

**Resolution**: Added all required dependencies to requirements-lambda.txt

### 4. Missing Environment Variable
**Issue**: NameError: 'os' is not defined in main.py

**Resolution**: Added missing `import os` statement

### 5. Metadata Structure Mismatch
**Issue**: KeyError: 'metadata' - Lambda expecting nested structure
```python
# Code expected:
metadata['metadata']  # nested structure

# Actual file had:
{
  "chunk_ids": [...],
  "dimension": 1536,
  "metadata": [...]  # correct structure
}
```

**Resolution**: Uploaded correct metadata.json structure from local data directory

### 6. CORS Configuration
**Issue**: Frontend couldn't access API due to CORS errors

**Resolution**: Configured API Gateway CORS settings to allow all origins

### 7. S3 Public Access
**Issue**: 403 Forbidden when accessing docerate.com (S3 static website)

**Resolution**:
- Disabled Block Public Access on S3 bucket
- Added bucket policy for public read access

### 8. API Endpoint Configuration
**Issue**: API subdomain (api.docerate.com) not configured

**Current State**:
- API accessible at: https://9o9ra1wg7f.execute-api.us-east-1.amazonaws.com/prod/
- Route 53 A record for api.docerate.com needs to be created

### 9. Environment Variable Mismatches
**Issue**: Lambda looking for wrong environment variable names
- Code expected: `EMBEDDING_MODEL`
- Lambda had: `BEDROCK_EMBEDDING_MODEL`

**Resolution**: Updated Lambda environment variables to match code expectations

### 10. AWS Bedrock Access Issues
**Issue**: AccessDeniedException when calling Bedrock InvokeModel
```
You don't have access to the model with the specified model ID
```

**Root Cause**:
- Bedrock models need to be explicitly enabled in AWS account
- Models are not automatically available even with IAM permissions

**Attempted Solutions**:
1. Added IAM policy for Bedrock access:
```json
{
  "Effect": "Allow",
  "Action": ["bedrock:InvokeModel"],
  "Resource": [
    "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1",
    "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-*"
  ]
}
```

2. Verified models exist in region:
- amazon.titan-embed-text-v1 ✓
- anthropic.claude-3-haiku-20240307-v1:0 ✓

**Required Action**:
- Go to AWS Bedrock Console → Model access
- Request access to required models
- Wait for approval (usually instant for some models)

### 11. Lambda Layer for NumPy
**Issue**: NumPy package too large for Lambda deployment

**Resolution**: Created Lambda layer with NumPy to keep main package small

## Current Status

### Working Components ✅
- Lambda function deploys and initializes
- S3 data loading works
- API Gateway routing works
- CloudFront distribution active
- Frontend loads at docerate.com
- Health endpoint returns data
- Tags API endpoint works

### Issues Remaining ❌
1. **Bedrock Models Not Enabled**
   - Search fails with "AccessDeniedException"
   - LLM generation not available
   - Need to enable models in AWS Console

2. **API Subdomain Not Configured**
   - api.docerate.com DNS not set up
   - Frontend uses direct API Gateway URL

3. **LLM Service Shows as Offline**
   - Health check shows: `"llm": false`
   - Due to Bedrock access issues

## Recommended Next Steps

1. **Enable Bedrock Models**:
   ```bash
   # Navigate to: AWS Console → Bedrock → Model access
   # Request access to:
   # - amazon.titan-embed-text-v1
   # - anthropic.claude-3-haiku-20240307-v1:0
   ```

2. **Alternative: Use OpenRouter**:
   - Update Lambda environment to use OpenRouter instead of Bedrock
   - Requires OPENROUTER_API_KEY in Lambda environment

3. **Configure Route 53**:
   - Create A record for api.docerate.com pointing to API Gateway
   - Update frontend to use api.docerate.com instead of direct URL

4. **Monitoring Setup**:
   - Configure CloudWatch alarms for Lambda errors
   - Set up API Gateway access logs
   - Monitor Lambda cold starts and memory usage

## Deployment Commands Reference

```bash
# Build and deploy Lambda
cd /home/donald/Projects/dontron_blog
./scripts/deploy-lambda.sh

# Deploy frontend
cd rag-frontend
npm run build
aws s3 sync build/ s3://docerate-frontend/ --delete

# Invalidate CloudFront cache
DIST_ID=$(aws cloudfront list-distributions --query "DistributionList.Items[?Aliases.Items[?contains(@,'docerate.com')]].Id" --output text)
aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"

# Update Lambda configuration
aws lambda update-function-configuration --function-name docerate-rag-api \
  --memory-size 512 \
  --timeout 30

# Check Lambda logs
aws logs tail /aws/lambda/docerate-rag-api --follow
```

## Lessons Learned

1. **Pre-generate Embeddings**: Don't include heavy ML libraries in Lambda
2. **Test Locally First**: Use Lambda runtime Docker images for testing
3. **Check AWS Service Availability**: Not all services are automatically enabled
4. **Use Lambda Layers**: For large dependencies like NumPy
5. **Validate Data Structures**: Ensure consistency between local and production
6. **Monitor Cold Starts**: Lambda initialization can timeout with complex setups
7. **CORS is Critical**: Configure early to avoid debugging frontend issues

## Cost Considerations

Current monthly estimate:
- Lambda: ~$5-10 (depending on usage)
- API Gateway: ~$3.50 per million requests
- S3: ~$1 for storage
- CloudFront: ~$0.085 per GB transferred
- Route 53: $0.50 per hosted zone

Total: ~$10-20/month for low traffic

## Contact for Issues
For any deployment issues, check:
1. Lambda logs in CloudWatch
2. API Gateway execution logs
3. S3 bucket permissions
4. CloudFront distribution status