# CORS and Lambda Troubleshooting Guide

Quick reference for fixing common CORS and Lambda issues in production.

## Issue 1: CORS Preflight Failures (HTTP 400)

### Symptoms
- Browser shows "Failed to generate content. Please try again."
- Network tab shows OPTIONS request returning 400
- CloudWatch logs show: `OPTIONS /prod/api/generate 400`

### Root Cause
CORS preflight (OPTIONS) requests were being rejected because:
1. API Gateway allowed limited headers: `content-type, authorization, x-requested-with`
2. Browser was sending additional headers like `accept` that weren't allowed
3. FastAPI/Mangum in Lambda was returning 400 for OPTIONS requests

### Solution

**Step 1: Update API Gateway CORS Configuration**
```bash
aws apigatewayv2 update-api \
    --api-id YOUR_API_ID \
    --cors-configuration "AllowOrigins=*,AllowMethods=*,AllowHeaders=*,MaxAge=3600"
```

**Step 2: Add OPTIONS Handler in Lambda** (`backend/lambda_handler.py`)
```python
def lambda_handler(event, context):
    # Handle OPTIONS requests directly (CORS preflight)
    if event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS' or \
       event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': '*',
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Max-Age': '3600'
            },
            'body': ''
        }

    # Process regular requests through Mangum
    response = handler(event, context)
    return response
```

**Step 3: Update FastAPI CORS Middleware** (`backend/main.py`)
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specific domains from settings
    allow_credentials=False,  # MUST be False when using wildcard origins
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)
```

**Step 4: Redeploy Lambda**
```bash
LAMBDA_FUNCTION_NAME=docerate-rag-api \
LAMBDA_ROLE=your-lambda-role-arn \
S3_BUCKET=your-rag-data-bucket \
./scripts/deploy-lambda.sh
```

### Verification
```bash
# Test OPTIONS request
curl -X OPTIONS "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/generate" \
  -H "Origin: https://yourdomain.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,accept" \
  -v

# Should return:
# HTTP/2 200
# access-control-allow-origin: *
# access-control-allow-methods: *
# access-control-allow-headers: *
```

---

## Issue 2: "Illegal header value b'Bearer'"

### Symptoms
- Generate button fails with generic error
- CloudWatch logs show: `OpenRouter health check failed: Illegal header value b'Bearer '`
- Backend service shows as offline

### Root Cause
The OpenRouter API key was being read as a bytes object instead of a string, causing httpx to fail when constructing the Authorization header.

### Solution

**Step 1: Add API Key Validation** (`backend/services/openrouter.py`)
```python
def __init__(self):
    # Ensure API key is always a string, not bytes
    api_key = settings.openrouter_api_key
    if api_key is None or api_key == "":
        print(f"WARNING: OpenRouter API key is not set!")
        self.api_key = ""
    elif isinstance(api_key, bytes):
        self.api_key = api_key.decode('utf-8').strip()
    else:
        self.api_key = str(api_key).strip()

    # ... rest of init
```

**Step 2: Add Health Check Guard** (`backend/services/openrouter.py`)
```python
async def health_check(self) -> bool:
    """Check if OpenRouter service is available."""
    if not self.api_key:
        print("OpenRouter health check skipped: API key not configured")
        return False

    # ... rest of health check
```

**Step 3: Redeploy with API Key Explicitly Set**
```bash
# Read API key from .env.production
OPENROUTER_KEY=$(grep OPENROUTER_API_KEY .env.production | cut -d= -f2)

# Deploy with explicit API key
LAMBDA_FUNCTION_NAME=docerate-rag-api \
LAMBDA_ROLE=your-lambda-role-arn \
S3_BUCKET=your-rag-data-bucket \
OPENROUTER_API_KEY="$OPENROUTER_KEY" \
./scripts/deploy-lambda.sh
```

### Verification
```bash
# Test health endpoint
curl https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/health | jq

# Should return:
# {
#   "status": "healthy",
#   "services": {
#     "search_index": true,
#     "embeddings": true,
#     "llm": true  # ← Should be true now
#   }
# }
```

---

## Quick Diagnostic Commands

### Check API Gateway CORS Configuration
```bash
aws apigatewayv2 get-api --api-id YOUR_API_ID --query 'CorsConfiguration'
```

### View Lambda Environment Variables
```bash
aws lambda get-function-configuration \
    --function-name docerate-rag-api \
    --query 'Environment.Variables' --output json
```

### Tail Lambda Logs
```bash
# Follow logs in real-time
aws logs tail /aws/lambda/docerate-rag-api --follow

# Filter for errors
aws logs tail /aws/lambda/docerate-rag-api --filter-pattern "ERROR"

# Search for specific errors
aws logs tail /aws/lambda/docerate-rag-api --since 30m | grep "Bearer\|CORS\|OPTIONS"
```

### Test API Endpoints
```bash
# Health check
curl -s https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/health | jq

# OPTIONS request (CORS preflight)
curl -X OPTIONS https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/generate \
  -H "Origin: https://yourdomain.com" \
  -H "Access-Control-Request-Method: POST" \
  -v

# Generate request
curl -X POST https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/generate \
  -H "Content-Type: application/json" \
  -d '{"query":"","tags":["AI"]}' | jq
```

---

## Common CORS Pitfalls

### ❌ **Don't**: Use `allow_credentials=True` with wildcard origins
```python
# This will cause CORS errors!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,  # ❌ Incompatible with wildcard
)
```

### ✅ **Do**: Set `allow_credentials=False` with wildcard
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # ✅ Works with wildcard
)
```

### ❌ **Don't**: Limit allowed headers in production
```python
# Limited headers may break browser requests
allow_headers=["content-type", "authorization"]  # ❌
```

### ✅ **Do**: Allow all headers or explicitly list common ones
```python
allow_headers=["*"]  # ✅ Works with all browsers
```

### ❌ **Don't**: Forget to handle OPTIONS in Lambda
API Gateway's CORS config alone isn't enough when using Lambda proxy integration.

### ✅ **Do**: Handle OPTIONS requests in lambda_handler
```python
if event.get('httpMethod') == 'OPTIONS':
    return {'statusCode': 200, 'headers': {...}}
```

---

## Prevention Checklist

Before deploying to production:

- [ ] API Gateway CORS allows all necessary headers (`*` recommended)
- [ ] Lambda handler intercepts and handles OPTIONS requests
- [ ] FastAPI CORS middleware configured correctly
- [ ] `allow_credentials=False` when using wildcard origins
- [ ] Environment variables properly set (not empty or bytes)
- [ ] Health endpoint returns 200 with all services showing true
- [ ] Test OPTIONS request returns 200 with proper headers
- [ ] Test actual generate request works end-to-end

---

## Files Changed to Fix Issues

1. **`backend/main.py:78-88`** - Updated CORS middleware configuration
2. **`backend/lambda_handler.py:41-52`** - Added OPTIONS request handler
3. **`backend/services/openrouter.py:15-29`** - Added API key validation
4. **`backend/services/openrouter.py:120-122`** - Added health check guard

All changes are included in the latest Lambda deployment.
