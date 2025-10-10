# AWS Services & Infrastructure Overview

This project relies on a small collection of managed AWS services to publish the AI-assisted blog and its associated API. The sections below describe each component, how it is configured, and why it exists.

## Amazon S3
- **docerate-frontend** – static hosting bucket for the built React application. Deployed via `scripts/deploy-frontend.sh`, fronted by CloudFront. Objects are uploaded with long-lived cache headers except for `index.html`/JSON which remain un-cached for fast version rollout.
- **docerate-rag-data** – stores Retrieval-Augmented Generation artifacts (chunk metadata, embeddings, BM25 index, summaries). The Lambda function downloads these files at cold start to serve search and generation requests.

## Amazon CloudFront
- Sits in front of the S3 frontend bucket to provide global CDN caching, TLS termination, and custom domain support (docerate.com). Invalidation is triggered automatically from the deploy script after each frontend sync.

## Amazon API Gateway (HTTP API)
- Provides the public HTTPS endpoint for the FastAPI backend (`https://9o9ra1wg7f.execute-api.us-east-1.amazonaws.com/prod`).
- Handles CORS preflight responses and stage prefixing (`/prod`).
- Integrates directly with Lambda without additional containers or EC2 instances.

## AWS Lambda
- **Function:** `docerate-rag-api` – runs the FastAPI application via Mangum. Reads RAG artifacts from S3, Markdown posts packaged in the deployment bundle, uses Bedrock for embeddings, and invokes OpenRouter for article generation.
- **Environment configuration:** managed by `scripts/deploy-lambda.sh`, which merges existing environment variables, sets S3/data directories, OpenRouter credentials, and Stage information for API Gateway routing.

### Lambda Layer
- **Layer:** `docerate-numpy-layer` – supplies a pre-built NumPy distribution to keep the Lambda deployment package below the size limit. The deploy script strips any bundled NumPy before zipping the function.

## Amazon CloudWatch Logs
- Collects structured logs from the Lambda function for request tracing, debugging Bedrock/OpenRouter calls, and monitoring OPTIONS/CORS behavior.

## Amazon Route 53
- Manages DNS for `docerate.com` (points to CloudFront) and `api.docerate.com` (points to API Gateway). Enables clean domains for both the UI and API.

## AWS Identity & Access Management (IAM)
- **Execution Role:** `docerate-rag-lambda-role` – grants Lambda the ability to read from the S3 data bucket, call Bedrock models, and emit CloudWatch logs.
- Custom managed policy (`docerate-rag-lambda-policy`) attaches S3 read permission and Bedrock invocation rights.

## Amazon Bedrock
- Provides managed embedding models (e.g., `amazon.titan-embed-text-v2:0`) used to compute query vectors and hybrid search reranking. Invoked directly from the Lambda function via the Bedrock Runtime SDK.

## Deployment Tooling (Local)
Although not hosted on AWS, the following local tooling orchestrates the deployment:
- **AWS CLI:** configured via `~/.aws/` credentials; all deploy scripts call the CLI to update Lambda, sync S3 buckets, and invalidate CloudFront.
- **GitHub Actions (optional):** A new workflow (`.github/workflows/deploy-rag-blog.yml`) can be wired to automate frontend/backend deploys if desired.

## External Dependencies
- **OpenRouter:** third-party LLM API for article generation. Credentials are stored as Lambda environment variables during deployment.

Together these services deliver a fully serverless stack: a globally cached static frontend, an API powered by Lambda, Bedrock/LLM integrations for AI features, and S3-stored RAG data for efficient retrieval.
