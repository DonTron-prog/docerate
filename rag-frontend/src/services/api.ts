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

export interface PostSummary {
  slug: string;
  title: string;
  date: string;
  tags: string[];
  category: string;
  description: string;
  image?: string;
  excerpt: string;
  reading_time: number;
}

export interface PostDetail {
  slug: string;
  title: string;
  date: string;
  tags: string[];
  category: string;
  description: string;
  image?: string;
  content: string;
  html_content: string;
  reading_time: number;
  metadata?: Record<string, any>;
}

export interface PostListResponse {
  posts: PostSummary[];
  total: number;
  page: number;
  per_page: number;
  has_more: boolean;
}

export interface PostsByTagResponse {
  tag: string;
  posts: PostSummary[];
  total: number;
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
    const baseUrl = API_BASE_URL ? API_BASE_URL.replace(/\/$/, '') : '';
    const params = new URLSearchParams({
      query: request.query,
      ...(request.tags.length ? { tags: request.tags.join(',') } : {}),
      ...(request.context ? { context: request.context } : {}),
    });

    const streamUrl = `${baseUrl}/api/generate/stream?${params.toString()}`;

    return new EventSource(streamUrl);
  }

  async checkHealth(): Promise<boolean> {
    try {
      const response = await this.axiosInstance.get('/health');
      return response.data.status === 'healthy';
    } catch {
      return false;
    }
  }

  // Blog post methods
  async getPosts(page: number = 1, perPage: number = 10): Promise<PostListResponse> {
    const response = await this.axiosInstance.get('/api/posts', {
      params: { page, per_page: perPage },
    });
    return response.data;
  }

  async getPost(slug: string): Promise<PostDetail> {
    const response = await this.axiosInstance.get(`/api/posts/${slug}`);
    return response.data;
  }

  async getRecentPosts(limit: number = 5): Promise<PostSummary[]> {
    const response = await this.axiosInstance.get('/api/posts/recent', {
      params: { limit },
    });
    return response.data;
  }

  async getPostsByTag(tag: string): Promise<PostsByTagResponse> {
    const response = await this.axiosInstance.get(`/api/posts/by-tag/${tag}`);
    return response.data;
  }
}

export const apiService = new ApiService();
export default apiService;
