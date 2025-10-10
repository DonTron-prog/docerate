/**
 * Static API service for fetching pre-generated JSON data.
 * This service fetches static JSON files directly from the public folder,
 * avoiding Lambda calls for blog content.
 */

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

export interface PostDetail extends PostSummary {
  content: string;
  html_content: string;
  metadata?: Record<string, any>;
}

export interface PostsIndex {
  posts: PostSummary[];
  total: number;
  generated_at: string;
}

export interface TagsIndex {
  tags: TagInfo[];
  total: number;
  generated_at: string;
}

export interface TagInfo {
  name: string;
  count: number;
  posts: string[];
}

export interface PostsByTag {
  tag: string;
  posts: PostSummary[];
  total: number;
}

class StaticApiService {
  private baseUrl: string;
  private cache: Map<string, any>;

  constructor() {
    // Use relative URL to fetch from the same domain (CloudFront)
    this.baseUrl = '/static-data';
    this.cache = new Map();
  }

  /**
   * Fetch JSON data with caching
   */
  private async fetchJson<T>(path: string, useCache: boolean = true): Promise<T> {
    const cacheKey = path;

    if (useCache && this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey);
    }

    try {
      const response = await fetch(`${this.baseUrl}${path}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();

      if (useCache) {
        this.cache.set(cacheKey, data);
      }

      return data;
    } catch (error) {
      console.error(`Failed to fetch ${path}:`, error);
      throw error;
    }
  }

  /**
   * Get all posts (from index)
   */
  async getPosts(): Promise<PostsIndex> {
    return this.fetchJson<PostsIndex>('/posts-index.json');
  }

  /**
   * Get a single post by slug
   */
  async getPost(slug: string): Promise<PostDetail> {
    return this.fetchJson<PostDetail>(`/posts/${slug}.json`);
  }

  /**
   * Get all tags with counts
   */
  async getTags(): Promise<TagsIndex> {
    return this.fetchJson<TagsIndex>('/tags-index.json');
  }

  /**
   * Get posts by tag
   */
  async getPostsByTag(tag: string): Promise<PostsByTag> {
    const tagSlug = tag.toLowerCase().replace(' ', '-');
    return this.fetchJson<PostsByTag>(`/tags/${tagSlug}.json`);
  }

  /**
   * Clear the cache
   */
  clearCache(): void {
    this.cache.clear();
  }

  /**
   * Check if static data is available
   */
  async isAvailable(): Promise<boolean> {
    try {
      const index = await this.fetchJson<PostsIndex>('/posts-index.json', false);
      return index && index.posts !== undefined;
    } catch {
      return false;
    }
  }
}

// Create a singleton instance
export const staticApi = new StaticApiService();
export default staticApi;