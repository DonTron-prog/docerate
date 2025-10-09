# Application Interaction Flow

```mermaid
sequenceDiagram
    participant User as User Browser
    participant Frontend as React Frontend (CloudFront)
    participant API as FastAPI Lambda
    participant Data as RAG Artifacts (S3)
    participant Content as Markdown Posts / Images
    participant Bedrock as Bedrock Embeddings
    participant OpenRouter as OpenRouter LLM

    User->>Frontend: Load AI Explorer / Blog Posts
    Frontend->>API: GET /api/tags
    API->>Data: Load cached tags
    API-->>Frontend: Tag list (counts)

    User->>Frontend: Submit search or generation request
    Frontend->>API: POST /api/search or /api/generate
    API->>Data: Retrieve embeddings & BM25 index
    API->>Content: Fetch post metadata / content
    API->>Bedrock: Embed query / rerank
    API->>OpenRouter: Generate article
    API-->>Frontend: Results / Generated article
    Frontend-->>User: Render content

    Frontend->>API: GET /api/posts, /api/posts/{slug}
    API->>Content: Read Markdown, render HTML
    API-->>Frontend: Post summaries / details
```

> **Overview:** The React frontend calls the Lambda-backed FastAPI API via CloudFront. Lambda reads RAG artifacts from S3, Markdown content from the packaged assets/S3, uses Bedrock for embeddings, and invokes OpenRouter for article generation before returning data to the client.
