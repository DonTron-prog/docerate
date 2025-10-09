# Lambda Package Files Explanation

## Why So Many Files?

The Lambda deployment consists of:

### 1. `lambda_package/` directory (120MB, 70+ subdirectories)
This directory contains:
- All Python dependencies needed for Lambda runtime
- FastAPI, boto3, pydantic, httpx, and other required libraries
- Your backend code copied into it
- The rag module for search functionality

**Purpose**: This is the staging directory where all code and dependencies are collected before zipping.

### 2. `lambda_function.zip` (40MB)
- Compressed version of the lambda_package directory
- This is what actually gets uploaded to AWS Lambda
- Compression reduces 120MB → 40MB (66% reduction)

### 3. `requirements-lambda.txt`
- Lists only the dependencies needed for Lambda runtime
- Excludes heavy ML libraries (PyTorch, sentence-transformers)
- Optimized to keep package size under Lambda's 250MB limit

## Why Not Use Virtual Environment?

Lambda needs:
- Specific directory structure
- No virtual environment activation
- All dependencies at the root level
- Platform-specific binaries (Linux x86_64)

## Build Process

The `scripts/deploy-lambda.sh` script:
1. Creates `lambda_package/` directory
2. Installs dependencies from `requirements-lambda.txt`
3. Copies backend code and rag modules
4. Creates `lambda_handler.py` at root level
5. Zips everything into `lambda_function.zip`
6. Uploads to AWS Lambda

## Why Keep These Files?

**During Development**:
- Quick redeployment without rebuilding
- Easy inspection of what's being deployed
- Debugging deployment issues

**For Production**:
- Should be built fresh in CI/CD pipeline
- Can be deleted after successful deployment
- Already excluded from git via .gitignore

## Cleanup Commands

If you want to remove these files after deployment:

```bash
# Remove build artifacts
rm -rf lambda_package/
rm lambda_function.zip

# Or use the deployment script with cleanup
./scripts/deploy-lambda.sh --clean
```

## Storage Impact

- **Local disk**: ~160MB total (120MB uncompressed + 40MB zip)
- **Git repository**: 0 bytes (excluded via .gitignore)
- **AWS Lambda**: 40MB (only the zip is uploaded)

## Best Practices

1. **Don't commit these files** - They're build artifacts
2. **Rebuild for production** - Dependencies may need updates
3. **Use Lambda Layers** - For large dependencies like NumPy
4. **Clean after deployment** - Save disk space locally
5. **Document dependencies** - Keep requirements-lambda.txt updated