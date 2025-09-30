import axios from 'axios';

// Use relative URLs to leverage the proxy configuration in package.json
const API_BASE_URL = process.env.REACT_APP_API_URL || '';

export interface Tag {
  name: string;
  count: number;
  description?: string;
}

export interface SearchResult {
  chunk_id: string;
  content: string;
  score: number;
  metadata: {
    post_slug: string;
    post_title: string;
    section_heading?: string;
    tags: string[];
    url_fragment: string;
    position: number;
  };
  source_type: string;
}

export interface GenerateRequest {
  query: string;
  tags: string[];
  context?: string;
  max_tokens?: number;
  temperature?: number;
}

export interface GenerateResponse {
  article: string;
  references: Reference[];
  generation_time_ms: number;
  model_used: string;
  chunks_retrieved: number;
}

export interface Reference {
  chunk_id: string;
  post_title: string;
  post_slug: string;
  section_heading?: string;
  url: string;
}

class ApiService {
  private axiosInstance = axios.create({
    baseURL: API_BASE_URL,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  async getTags(): Promise<Tag[]> {
    const response = await this.axiosInstance.get('/api/tags');
    return response.data.tags;
  }

  async search(query: string, tags: string[] = [], limit: number = 5): Promise<SearchResult[]> {
    const response = await this.axiosInstance.post('/api/search', {
      query,
      tags,
      limit,
    });
    return response.data.results;
  }

  async generate(request: GenerateRequest): Promise<GenerateResponse> {
    const response = await this.axiosInstance.post('/api/generate', request);
    return response.data;
  }

  async generateStream(request: GenerateRequest): Promise<EventSource> {
    const eventSource = new EventSource(
      `/api/generate/stream?${new URLSearchParams({
        query: request.query,
        tags: request.tags.join(','),
        ...(request.context && { context: request.context }),
      })}`
    );
    return eventSource;
  }

  async checkHealth(): Promise<boolean> {
    try {
      const response = await this.axiosInstance.get('/health');
      return response.data.status === 'healthy';
    } catch {
      return false;
    }
  }
}

export default new ApiService();