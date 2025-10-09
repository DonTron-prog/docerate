# Local Development Setup

```mermaid
flowchart LR
    subgraph DevMachine[Developer Workstation]
        Editor[IDE / Editor]
        Shell[Terminal]
        BrowserLocal[Local Browser]
    end

    subgraph LocalServices[Local Services]
        BackendLocal["FastAPI App (uvicorn)"]
        FrontendLocal["React Dev Server (npm start)"]
        DockerCompose[(Docker Compose)]
    end

    subgraph LocalData[Local Data & Tools]
        LocalContent["Markdown Posts (content/posts)"]
        LocalImages["Images (content/images)"]
        LocalDataDir["RAG Artifacts (data/*)"]
        Ollama["Ollama Server (optional)"]
    end

    subgraph AWSAccess[AWS Credentials]
        AWSCLI[AWS CLI]
        LocalAWSConfig[(~/.aws)]
    end

    Editor --> Shell
    Shell -->|run backend| BackendLocal
    Shell -->|run frontend| FrontendLocal
    Shell -->|docker-compose| DockerCompose

    BackendLocal --> LocalDataDir
    BackendLocal --> LocalContent
    BackendLocal --> LocalImages
    BackendLocal -->|optional LLM| Ollama

    FrontendLocal --> BrowserLocal
    BrowserLocal -->|API calls| BackendLocal

    Shell --> AWSCLI
    AWSCLI --> LocalAWSConfig
    AWSCLI -->|deploy scripts| AWSCloud[(AWS Account)]

    DockerCompose --> BackendLocal
    DockerCompose --> OtherServices[(Supporting Containers)]
```

> **Usage:** run `npm start` inside `rag-frontend/` for the React UI and `uvicorn backend.main:app --reload` (or `docker-compose up`) for the FastAPI backend. Local content, images, and RAG artifacts are loaded from the repository’s `content/` and `data/` directories.
