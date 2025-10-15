# CloudFront API Routing - Eliminating CORS

This document explains how we've configured CloudFront to route API requests, eliminating the need for CORS (Cross-Origin Resource Sharing) in both production and local development.

## Problem: Why CORS Was Needed Before

### Old Architecture
```
Frontend: https://d2w8hymo03zbys.cloudfront.net (CloudFront)
API:      https://9o9ra1wg7f.execute-api.us-east-1.amazonaws.com/prod (API Gateway)
          ↑
          Different domains = Cross-Origin Request
```

**Issues:**
- Two different domains triggered browser CORS restrictions
- Required complex CORS middleware in backend
- Easy to misconfigure (Access-Control-Allow-Origin, methods, headers, etc.)
- OPTIONS preflight requests for POST/PUT/DELETE
- Security concerns with wildcard CORS

## Solution: Single-Origin Architecture

### New Architecture

#### Production
```
User → https://d2w8hymo03zbys.cloudfront.net
         ├─ /*        → S3 (frontend static files)
         └─ /api/*    → API Gateway → Lambda
                        ↑
                        Same origin - No CORS needed!
```

#### Local Development
```
User → http://localhost:3000 (React dev server)
         ├─ /static/*  → React app
         └─ /api/*     → Proxy to localhost:5000 (FastAPI)
                         ↑
                         Same origin - No CORS needed!
```

## How It Works

### CloudFront Configuration

CloudFront now has **two origins**:

1. **S3 Origin** (id: `S3-docerate-frontend`)
   - Domain: `docerate-frontend.s3-website-us-east-1.amazonaws.com`
   - Serves: Frontend static files (HTML, JS, CSS)

2. **API Gateway Origin** (id: `api-gateway-origin`)
   - Domain: `9o9ra1wg7f.execute-api.us-east-1.amazonaws.com`
   - Origin Path: `/prod` (strips stage from URL)
   - Serves: API requests

### Cache Behaviors

1. **Default Behavior**: `/*` → S3 Origin
   - All static content (index.html, JS bundles, CSS, images)

2. **API Behavior**: `/api/*` → API Gateway Origin
   - All API endpoints
   - No caching (TTL = 0)
   - Forwards all headers, query strings, cookies
   - Allows all HTTP methods (GET, POST, PUT, DELETE, PATCH, OPTIONS)

### Local Development Proxy

In `rag-frontend/package.json`:
```json
"proxy": "http://localhost:5000"
```

The React dev server automatically proxies `/api/*` requests to the backend, creating same-origin behavior.

## Benefits

✅ **No CORS Complexity**
- No middleware needed in backend
- No configuration of allowed origins
- No preflight OPTIONS requests

✅ **Better Security**
- Single entry point through CloudFront
- No wildcard CORS origins
- CloudFront WAF can protect both frontend and API

✅ **Consistent Architecture**
- Same pattern in production and local dev
- Easier to reason about

✅ **Better Performance** (Optional)
- Can enable caching for GET API requests
- CloudFront edge locations for API calls
- Reduced latency globally

✅ **Simpler Code**
- Cleaner backend (no CORS middleware)
- Frontend uses relative URLs everywhere
- Less configuration to maintain

## Setup Instructions

### Initial Setup (One-time)

1. **Configure CloudFront routing:**
   ```bash
   ./scripts/update-cloudfront-routing.sh
   ```

   This script:
   - Adds API Gateway as second origin
   - Creates cache behavior for `/api/*` paths
   - Updates distribution configuration
   - Waits for deployment (optional)

2. **Deploy updated frontend:**
   ```bash
   FRONTEND_BUCKET=docerate-frontend \
   CLOUDFRONT_DIST_ID=E3FV2HGEXHUM2J \
   ./scripts/deploy-frontend.sh
   ```

### Configuration Files

#### Frontend (.env files)
```bash
# rag-frontend/.env.production
REACT_APP_API_URL=
REACT_APP_ENVIRONMENT=production

# rag-frontend/.env.local
REACT_APP_API_URL=
REACT_APP_ENVIRONMENT=local
```

**Empty `REACT_APP_API_URL`** = use relative URLs = same origin routing.

#### Backend (No CORS)
The backend `main.py` no longer includes:
```python
# REMOVED - Not needed anymore!
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, ...)
```

## Troubleshooting

### Frontend can't reach API in production

**Check:**
1. CloudFront cache behavior exists for `/api/*`
   ```bash
   aws cloudfront get-distribution-config --id E3FV2HGEXHUM2J | jq '.DistributionConfig.CacheBehaviors'
   ```

2. API Gateway origin exists
   ```bash
   aws cloudfront get-distribution-config --id E3FV2HGEXHUM2J | jq '.DistributionConfig.Origins.Items[] | select(.Id == "api-gateway-origin")'
   ```

3. Frontend is using relative URLs (check browser network tab)

### Local dev can't reach API

**Check:**
1. Proxy configuration in `package.json`:
   ```json
   "proxy": "http://localhost:5000"
   ```

2. Backend is running on port 5000:
   ```bash
   uvicorn backend.main:app --reload --port 5000
   ```

3. Frontend is using relative URLs (empty `REACT_APP_API_URL`)

### API returns 403 or 404

**Check:**
1. Origin path is `/prod` (strips stage from URL)
2. Lambda environment has correct configuration
3. API Gateway stage is `prod`

### CloudFront returns stale API responses

**Solution:** Invalidate CloudFront cache:
```bash
aws cloudfront create-invalidation \
  --distribution-id E3FV2HGEXHUM2J \
  --paths "/api/*"
```

Or set shorter TTL for API cache behavior if caching is enabled.

## Architecture Decision

### Why Not Use API Gateway Custom Domain?

You might wonder: why not just use API Gateway custom domain (e.g., `api.docerate.com`)?

**Reasons for CloudFront routing:**
1. **Single Entry Point**: All traffic through CloudFront (unified WAF, logging, monitoring)
2. **Simpler DNS**: Only one domain to manage
3. **Better Caching**: CloudFront caching closer to users than API Gateway
4. **Cost**: CloudFront + API Gateway cheaper than API Gateway custom domain + CloudFront
5. **Flexibility**: Easy to switch backends without DNS changes

### Performance Considerations

**API Request Path:**
```
User → CloudFront Edge → API Gateway → Lambda
       (closest POP)      (us-east-1)
```

**Latency:**
- **CloudFront overhead**: ~5-10ms (minimal)
- **Cache hit** (if enabled): ~50-100ms (edge to user)
- **Cache miss**: Same as direct API Gateway call

**Recommendation:**
- Dynamic data: No caching (TTL=0) ✅ Current setup
- Static API data: Short TTL (60-300s) for cost savings

## Monitoring

### CloudWatch Metrics

Monitor these CloudFront metrics:
- `Requests` (split by `/api/*` behavior)
- `BytesDownloaded`
- `4xxErrorRate` / `5xxErrorRate`
- `CacheHitRate` (if caching enabled)

### Logging

Enable CloudFront access logs to track API usage:
```bash
aws cloudfront update-distribution \
  --id E3FV2HGEXHUM2J \
  --logging-config \
    Enabled=true,Bucket=my-logs-bucket.s3.amazonaws.com,Prefix=cloudfront/
```

## Cost Impact

**Before (CORS):**
- Direct API Gateway calls: $3.50 per million requests
- Data transfer: $0.09/GB

**After (CloudFront Routing):**
- CloudFront requests: $0.01 per 10,000 requests
- API Gateway calls: $3.50 per million requests (same)
- Data transfer: $0.085/GB (slightly cheaper via CloudFront)

**Net Impact:** Minimal cost increase (~$1-2/month) with potential for savings if caching is enabled for GET requests.

## References

- [CloudFront Cache Behaviors](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-web-values-specify.html#DownloadDistValuesCacheBehavior)
- [API Gateway with CloudFront](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-content-encodings-examples-cloudfront.html)
- [React Proxy in Development](https://create-react-app.dev/docs/proxying-api-requests-in-development/)
- [CORS MDN Documentation](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)

## Migration Checklist

- [x] Create CloudFront update script
- [x] Remove CORS middleware from backend
- [x] Update frontend .env files
- [x] Configure React dev server proxy
- [ ] Run CloudFront update script
- [ ] Deploy updated frontend
- [ ] Test production API calls
- [ ] Test local development
- [ ] Monitor for CORS errors
- [ ] Update team documentation

## Support

For issues or questions about CloudFront API routing:
1. Check this document's troubleshooting section
2. Review CloudFront distribution configuration
3. Check browser network tab for request details
4. Review CloudFront access logs (if enabled)
