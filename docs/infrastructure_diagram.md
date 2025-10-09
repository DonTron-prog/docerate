# Project Infrastructure Overview

```mermaid
flowchart LR
    subgraph UserSide[Client Side]
        U[User Browser]
    end

    subgraph Delivery[Content Delivery]
        CF[CloudFront Distribution]
        S3Frontend[S3 Bucket<br/>docerate-frontend]
    end

    subgraph ApiTier[API Tier]
        APIGW[API Gateway<br/>HTTP API]
        LAMBDA[Lambda Function<br/>docerate-rag-api]
        LAYER[Lambda Layer<br/>docerate-numpy-layer]
    end

    subgraph DataServices[Data & AI Services]
        S3Data[S3 Bucket<br/>docerate-rag-data]
        Bedrock[AWS Bedrock<br/>Titan Embeddings]
        OpenRouter[OpenRouter<br/>LLM API]
    end

    subgraph Observability[Logs]
        CW[CloudWatch Logs]
    end

    subgraph DNSRouting[DNS]
        Route53[Route 53]
        Domain[(docerate.com)]
        APIDomain[(api.docerate.com)]
    end

    U -->|HTTPS requests| CF
    CF -->|Static assets| S3Frontend
    CF -->|API requests| APIGW

    APIGW --> LAMBDA
    LAMBDA -->|Mounted layer| LAYER
    LAMBDA -->|Load index artifacts| S3Data
    LAMBDA -->|Embedding calls| Bedrock
    LAMBDA -->|Generation calls| OpenRouter
    LAMBDA -->|Structured logs| CW

    Domain --> Route53
    APIDomain --> Route53
    Route53 --> CF
    Route53 --> APIGW
```

> **Note:** Route 53 routes `docerate.com` and `api.docerate.com` to CloudFront and API Gateway respectively. Lambda reads pre-generated RAG artifacts from `docerate-rag-data` and uses Bedrock for embeddings plus OpenRouter for article generation.
