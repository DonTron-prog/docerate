# Architecture Improvement Recommendations

Based on software engineering best practices, here are prioritized recommendations to improve the Docerate RAG architecture.

## 🔴 High Priority (Do First)

### 1. Fix CloudFront API Routing
**Current Issue**: Frontend makes cross-origin requests directly to API Gateway instead of going through CloudFront.

**Problem**:
- Unnecessary CORS complexity
- Two separate domains (CloudFront for frontend, API Gateway for API)
- Not leveraging CloudFront's global edge network for API caching

**Recommended Architecture**:
```
User → CloudFront → /api/* → API Gateway → Lambda
                  → /* → S3 (static content)
```

**Implementation**:
```bash
# Add API Gateway as second origin to CloudFront
aws cloudfront update-distribution --id YOUR_DIST_ID \
  --distribution-config file://updated-config.json

# Create cache behavior for /api/* paths
# Route to API Gateway origin with:
# - No caching (or short TTL for GET requests)
# - Forward all headers/query strings
# - Allow POST/GET/OPTIONS methods
```

**Benefits**:
- ✅ Single domain (no CORS issues)
- ✅ CloudFront edge caching for API responses
- ✅ Better security (can use CloudFront signed URLs)
- ✅ Simpler frontend configuration

**Files to Update**:
- `rag-frontend/.env.production`: Change to relative URLs or empty
- `rag-frontend/src/services/api.ts`: Use relative paths

---

### 2. Implement Proper Environment Separation
**Current Issue**: Single production environment with manual configuration.

**Recommended Structure**:
```
environments/
├── dev/
│   ├── terraform.tfvars
│   └── backend.tf
├── staging/
│   ├── terraform.tfvars
│   └── backend.tf
└── prod/
    ├── terraform.tfvars
    └── backend.tf
```

**Implementation Using Infrastructure as Code (Terraform)**:
```hcl
# terraform/main.tf
module "docerate" {
  source = "./modules/docerate-stack"

  environment         = var.environment
  s3_frontend_bucket  = "${var.project_name}-frontend-${var.environment}"
  s3_data_bucket      = "${var.project_name}-rag-data-${var.environment}"
  lambda_function_name = "${var.project_name}-api-${var.environment}"

  # Environment-specific overrides
  lambda_memory       = var.environment == "prod" ? 1024 : 512
  lambda_timeout      = var.environment == "prod" ? 60 : 30
}
```

**Benefits**:
- ✅ Test changes in dev/staging before production
- ✅ Consistent infrastructure across environments
- ✅ Easy rollback and disaster recovery
- ✅ Infrastructure versioning

---

### 3. Add Comprehensive Error Handling
**Current Issue**: Generic error messages, limited error context.

**Recommended Approach**:

**Backend Error Handler** (`backend/middleware/error_handler.py`):
```python
from fastapi import Request, status
from fastapi.responses import JSONResponse
import traceback
import logging

logger = logging.getLogger(__name__)

async def error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global error handler with structured logging."""

    # Log full error with context
    logger.error(
        f"Request failed: {request.method} {request.url.path}",
        extra={
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "path": request.url.path,
            "method": request.method,
            "client_host": request.client.host,
            "traceback": traceback.format_exc()
        }
    )

    # Don't expose internal errors to users
    if isinstance(exc, ValueError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Invalid request",
                "detail": str(exc),
                "code": "INVALID_REQUEST"
            }
        )

    # Service unavailable errors
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "Service temporarily unavailable",
                "detail": "External service error",
                "code": "SERVICE_UNAVAILABLE",
                "retry_after": 60
            }
        )

    # Generic 500 error
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "code": "INTERNAL_ERROR",
            "request_id": request.headers.get("x-request-id")
        }
    )

# Register in main.py
app.add_exception_handler(Exception, error_handler)
```

**Add Request ID Middleware** (`backend/middleware/request_id.py`):
```python
import uuid
from fastapi import Request

async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response

app.middleware("http")(add_request_id)
```

**Benefits**:
- ✅ Better debugging with request tracing
- ✅ User-friendly error messages
- ✅ Structured logging for analysis
- ✅ Security (no sensitive info exposure)

---

### 4. Add Secrets Management
**Current Issue**: API keys in environment variables and code.

**Recommended**: Use AWS Secrets Manager

**Implementation**:
```python
# backend/config.py
import boto3
import json
from functools import lru_cache

@lru_cache()
def get_secret(secret_name: str) -> dict:
    """Fetch secrets from AWS Secrets Manager with caching."""
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

class Settings(BaseSettings):
    # ... existing settings

    @property
    def openrouter_api_key(self) -> str:
        if self.environment == "production":
            secrets = get_secret("docerate/production/api-keys")
            return secrets['openrouter_api_key']
        return os.getenv("OPENROUTER_API_KEY", "")
```

**Setup**:
```bash
# Create secret
aws secretsmanager create-secret \
    --name docerate/production/api-keys \
    --secret-string '{"openrouter_api_key":"sk-or-v1-..."}'

# Grant Lambda access
aws iam attach-role-policy \
    --role-name docerate-rag-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite
```

**Benefits**:
- ✅ Centralized secret management
- ✅ Automatic rotation support
- ✅ Audit trail for secret access
- ✅ No secrets in code or env vars

---

## 🟡 Medium Priority (Next Phase)

### 5. Implement API Caching
**Current Issue**: Every request hits Lambda, even for identical queries.

**Recommended**: Add ElastiCache (Redis) for response caching

**Architecture**:
```python
# backend/services/cache.py
import redis
import json
from typing import Optional
import hashlib

class CacheService:
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.redis_host,
            port=6379,
            decode_responses=True
        )

    def get_cached_response(self, query: str, tags: list) -> Optional[dict]:
        """Get cached response for query."""
        cache_key = self._get_cache_key(query, tags)
        cached = self.redis.get(cache_key)
        return json.loads(cached) if cached else None

    def cache_response(self, query: str, tags: list, response: dict, ttl: int = 3600):
        """Cache response for query."""
        cache_key = self._get_cache_key(query, tags)
        self.redis.setex(cache_key, ttl, json.dumps(response))

    def _get_cache_key(self, query: str, tags: list) -> str:
        """Generate cache key from query and tags."""
        key_data = f"{query}::{','.join(sorted(tags))}"
        return f"generate:{hashlib.md5(key_data.encode()).hexdigest()}"
```

**Alternative**: Use API Gateway caching (simpler but less control)
```bash
aws apigatewayv2 update-stage \
    --api-id YOUR_API_ID \
    --stage-name prod \
    --route-settings '*/GET/api/search={CachingEnabled=true,CacheTtlInSeconds=300}'
```

**Benefits**:
- ✅ Reduced Lambda invocations (cost savings)
- ✅ Faster response times
- ✅ Better user experience
- ✅ Reduced OpenRouter API costs

---

### 6. Add Observability Stack
**Current Issue**: Limited visibility into system behavior.

**Recommended**: Structured logging + metrics + tracing

**CloudWatch Structured Logging**:
```python
# backend/utils/logger.py
import json
import logging
from datetime import datetime

class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def log_event(self, event_type: str, **kwargs):
        """Log structured event."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            **kwargs
        }
        self.logger.info(json.dumps(log_entry))

# Usage
logger = StructuredLogger(__name__)
logger.log_event(
    "rag_query",
    query=query,
    tags=tags,
    chunks_retrieved=len(chunks),
    generation_time_ms=elapsed_ms,
    model=model_used
)
```

**CloudWatch Metrics**:
```python
# backend/utils/metrics.py
import boto3

cloudwatch = boto3.client('cloudwatch')

def emit_metric(metric_name: str, value: float, unit: str = 'Count'):
    """Emit custom CloudWatch metric."""
    cloudwatch.put_metric_data(
        Namespace='Docerate/RAG',
        MetricData=[{
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit,
            'Timestamp': datetime.utcnow()
        }]
    )

# Track key metrics
emit_metric('GenerationLatency', elapsed_ms, 'Milliseconds')
emit_metric('TokensGenerated', token_count, 'Count')
emit_metric('ChunksRetrieved', len(chunks), 'Count')
```

**CloudWatch Alarms**:
```bash
# Create alarm for Lambda errors
aws cloudwatch put-metric-alarm \
    --alarm-name docerate-lambda-errors \
    --alarm-description "Alert on Lambda errors" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 5 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=FunctionName,Value=docerate-rag-api
```

**Benefits**:
- ✅ Proactive issue detection
- ✅ Performance insights
- ✅ Usage analytics
- ✅ Cost optimization data

---

### 7. Implement Rate Limiting & Throttling
**Current Issue**: No protection against abuse or runaway costs.

**Recommended**: API Gateway throttling + DynamoDB token bucket

**API Gateway Throttling**:
```bash
aws apigatewayv2 update-stage \
    --api-id YOUR_API_ID \
    --stage-name prod \
    --throttle-settings RateLimit=100,BurstLimit=200
```

**Per-User Rate Limiting** (if using auth):
```python
# backend/middleware/rate_limit.py
from fastapi import Request, HTTPException
import boto3
from datetime import datetime, timedelta

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('docerate-rate-limits')

async def check_rate_limit(request: Request):
    """Check if user has exceeded rate limit."""
    user_id = request.state.user_id or request.client.host

    response = table.get_item(Key={'user_id': user_id})

    if 'Item' in response:
        item = response['Item']
        if item['request_count'] >= 100:  # 100 requests per hour
            if datetime.fromisoformat(item['window_start']) > datetime.utcnow() - timedelta(hours=1):
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Try again later.",
                    headers={"Retry-After": "3600"}
                )

    # Increment counter
    table.update_item(
        Key={'user_id': user_id},
        UpdateExpression='ADD request_count :inc SET window_start = :now',
        ExpressionAttributeValues={
            ':inc': 1,
            ':now': datetime.utcnow().isoformat()
        }
    )

app.middleware("http")(check_rate_limit)
```

**Benefits**:
- ✅ Cost protection
- ✅ Fair usage enforcement
- ✅ DDoS protection
- ✅ Predictable costs

---

### 8. Add Automated Testing
**Current Issue**: No tests, manual verification only.

**Recommended Test Structure**:
```
tests/
├── unit/
│   ├── test_embeddings.py
│   ├── test_search.py
│   └── test_generation.py
├── integration/
│   ├── test_api_endpoints.py
│   └── test_rag_pipeline.py
└── e2e/
    ├── test_user_flows.py
    └── test_deployment.py
```

**Example Unit Test**:
```python
# tests/unit/test_search.py
import pytest
from rag.search import HybridSearch

@pytest.fixture
def mock_search():
    # Create mock with sample data
    return HybridSearch(...)

def test_hybrid_search_combines_results(mock_search):
    """Test that hybrid search combines BM25 and vector results."""
    results = mock_search.search(query="test", top_k=5)

    assert len(results) == 5
    assert all(hasattr(r, 'score') for r in results)
    assert results[0].score >= results[-1].score  # Sorted by score

def test_search_filters_by_tags(mock_search):
    """Test tag filtering works correctly."""
    results = mock_search.search(query="test", filter_tags=["AI"])

    assert all("AI" in r.tags for r in results)
```

**Integration Test**:
```python
# tests/integration/test_api_endpoints.py
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_generate_endpoint_returns_article():
    """Test generate endpoint produces valid output."""
    response = client.post("/api/generate", json={
        "query": "",
        "tags": ["AI", "SRE"]
    })

    assert response.status_code == 200
    data = response.json()
    assert "article" in data
    assert "references" in data
    assert len(data["references"]) > 0
```

**Run Tests**:
```bash
# Install test dependencies
pip install pytest pytest-cov pytest-asyncio httpx

# Run tests
pytest tests/ -v --cov=backend --cov=rag

# CI/CD integration
pytest tests/ --junitxml=test-results.xml
```

**Benefits**:
- ✅ Catch bugs before deployment
- ✅ Refactoring confidence
- ✅ Documentation through examples
- ✅ CI/CD integration

---

## 🟢 Lower Priority (Nice to Have)

### 9. Implement CI/CD Pipeline
**Current Issue**: Manual deployments, no automation.

**Recommended**: GitHub Actions workflow

**`.github/workflows/deploy.yml`**:
```yaml
name: Deploy to AWS

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov

  deploy-staging:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v3
      - uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Deploy Lambda
        run: |
          LAMBDA_FUNCTION_NAME=docerate-rag-api-staging \
          LAMBDA_ROLE=${{ secrets.LAMBDA_ROLE_ARN }} \
          S3_BUCKET=docerate-rag-data-staging \
          ./scripts/deploy-lambda.sh

      - name: Deploy Frontend
        run: |
          cd rag-frontend
          npm ci
          npm run build
          aws s3 sync build/ s3://docerate-frontend-staging/

  deploy-production:
    needs: deploy-staging
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      # Same as staging, but with production resources
```

**Benefits**:
- ✅ Automated deployments
- ✅ Consistent builds
- ✅ Deploy on merge
- ✅ Environment promotion (staging → prod)

---

### 10. Add API Versioning
**Current Issue**: Breaking changes affect all users immediately.

**Recommended**: URL-based versioning

**Implementation**:
```python
# backend/main.py
from fastapi import APIRouter

# V1 API
v1_router = APIRouter(prefix="/api/v1")

@v1_router.post("/generate")
async def generate_v1(request: GenerateRequest):
    """Original generate endpoint."""
    # ... existing logic

# V2 API with improvements
v2_router = APIRouter(prefix="/api/v2")

@v2_router.post("/generate")
async def generate_v2(request: GenerateRequestV2):
    """Improved generate endpoint with streaming support."""
    # ... new logic

app.include_router(v1_router)
app.include_router(v2_router)

# Maintain /api/generate for backwards compatibility (points to v1)
app.include_router(v1_router, prefix="/api", tags=["legacy"])
```

**Benefits**:
- ✅ Backwards compatibility
- ✅ Gradual migrations
- ✅ Deprecation path
- ✅ A/B testing support

---

### 11. Optimize Lambda Cold Starts
**Current Issue**: 2-4 second cold starts affect UX.

**Recommended Optimizations**:

**1. Lambda SnapStart** (Java only, but similar concepts):
```bash
# Enable provisioned concurrency for consistent performance
aws lambda put-provisioned-concurrency-config \
    --function-name docerate-rag-api \
    --provisioned-concurrent-executions 2 \
    --qualifier PROD
```

**2. Reduce Package Size**:
```python
# backend/lambda_handler.py
import sys
import os

# Remove unnecessary modules before import
if 'pandas' in sys.modules:
    del sys.modules['pandas']

# Lazy load heavy dependencies
_openrouter_service = None

def get_openrouter_service():
    global _openrouter_service
    if _openrouter_service is None:
        from backend.services.openrouter import OpenRouterService
        _openrouter_service = OpenRouterService()
    return _openrouter_service
```

**3. Keep Lambda Warm**:
```python
# CloudWatch Event Rule to ping Lambda every 5 minutes
aws events put-rule \
    --name keep-docerate-lambda-warm \
    --schedule-expression 'rate(5 minutes)'

aws lambda add-permission \
    --function-name docerate-rag-api \
    --statement-id KeepWarm \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com
```

**Benefits**:
- ✅ Faster first response
- ✅ Better user experience
- ✅ More predictable latency

---

### 12. Implement Content Versioning & Rollback
**Current Issue**: No way to rollback bad content or index updates.

**Recommended**: S3 versioning + deployment tracking

**Enable S3 Versioning**:
```bash
aws s3api put-bucket-versioning \
    --bucket docerate-rag-data \
    --versioning-configuration Status=Enabled
```

**Track Deployments** (DynamoDB):
```python
# Track each index deployment
deployment_table.put_item(Item={
    'deployment_id': str(uuid.uuid4()),
    'timestamp': datetime.utcnow().isoformat(),
    'index_version': index_version,
    's3_objects': {
        'embeddings': embedding_version_id,
        'bm25': bm25_version_id,
        'chunks': chunks_version_id
    },
    'num_posts': len(posts),
    'num_chunks': len(chunks),
    'deployed_by': user
})
```

**Rollback Script**:
```bash
# scripts/rollback-index.sh
aws s3api list-object-versions \
    --bucket docerate-rag-data \
    --prefix embeddings.npy \
    --query 'Versions[1].VersionId' \
    | xargs -I {} aws s3api copy-object \
        --bucket docerate-rag-data \
        --copy-source docerate-rag-data/embeddings.npy?versionId={} \
        --key embeddings.npy
```

**Benefits**:
- ✅ Quick rollback on issues
- ✅ Audit trail
- ✅ Experiment safely
- ✅ Disaster recovery

---

## Implementation Priority Matrix

| Improvement | Impact | Effort | Priority | Timeline |
|-------------|--------|--------|----------|----------|
| Fix CloudFront API Routing | High | Medium | 1 | Week 1 |
| Environment Separation | High | High | 2 | Week 2-3 |
| Error Handling | High | Low | 3 | Week 1 |
| Secrets Management | High | Medium | 4 | Week 2 |
| API Caching | Medium | Medium | 5 | Week 3 |
| Observability | Medium | Medium | 6 | Week 3-4 |
| Rate Limiting | Medium | Low | 7 | Week 2 |
| Automated Testing | Medium | High | 8 | Week 4-5 |
| CI/CD Pipeline | Medium | Medium | 9 | Week 5 |
| API Versioning | Low | Low | 10 | Week 6 |
| Cold Start Optimization | Low | Medium | 11 | Week 6 |
| Content Versioning | Low | Medium | 12 | Week 7 |

---

## Quick Wins (Do This Week)

1. **Add error handling middleware** (2 hours)
2. **Enable CloudWatch structured logging** (1 hour)
3. **Set up CloudWatch alarms** (1 hour)
4. **Enable S3 versioning** (30 minutes)
5. **Add health check improvements** (1 hour)

**Total**: ~5-6 hours for significant reliability improvements

---

## Architecture Decision Records (ADRs)

For major changes, document decisions:

**`docs/adr/001-use-cloudfront-for-api.md`**:
```markdown
# ADR 001: Route API requests through CloudFront

## Status
Proposed

## Context
Currently frontend makes CORS requests directly to API Gateway, causing:
- Complex CORS configuration
- No API caching at edge
- Two separate domains

## Decision
Route all API requests through CloudFront using path-based routing.

## Consequences
Positive:
- Single domain, simplified CORS
- Edge caching for API responses
- Better global performance

Negative:
- More complex CloudFront configuration
- Need to invalidate cache on updates
```

---

## References

- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [12-Factor App](https://12factor.net/)
- [API Design Best Practices](https://www.apiguide.com/api-best-practices/)
