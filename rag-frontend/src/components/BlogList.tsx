import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { apiService } from '../services/api';
import './BlogList.css';

interface PostSummary {
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

interface BlogListProps {
  selectedTag?: string;
}

const BlogList: React.FC<BlogListProps> = ({ selectedTag }) => {
  const [posts, setPosts] = useState<PostSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPosts = async () => {
      try {
        setLoading(true);
        const data = selectedTag
          ? await apiService.getPostsByTag(selectedTag)
          : await apiService.getPosts();
        setPosts(data.posts);
      } catch (err) {
        setError('Failed to load blog posts');
        console.error('Error fetching posts:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPosts();
  }, [selectedTag]);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="blog-list-container">
        <div className="loading">Loading posts...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="blog-list-container">
        <div className="error">{error}</div>
      </div>
    );
  }

  if (posts.length === 0) {
    return (
      <div className="blog-list-container">
        <div className="no-posts">No posts found</div>
      </div>
    );
  }

  return (
    <div className="blog-list-container">
      {selectedTag && (
        <div className="filter-header">
          <h2>Posts tagged with "{selectedTag}"</h2>
          <Link to="/blog" className="clear-filter">Clear filter</Link>
        </div>
      )}

      <div className="posts-grid">
        {posts.map((post) => (
          <article key={post.slug} className="post-card">
            <Link to={`/blog/${post.slug}`} className="post-link">
              {post.image && (
                <div className="post-image">
                  <img src={post.image} alt={post.title} loading="lazy" />
                </div>
              )}
              <div className="post-content">
                <div className="post-header">
                  <h2 className="post-title">{post.title}</h2>
                  <div className="post-meta">
                    <time className="post-date">{formatDate(post.date)}</time>
                    <span className="reading-time">{post.reading_time} min read</span>
                  </div>
                </div>

                <p className="post-excerpt">{post.excerpt}</p>

                <div className="post-footer">
                  <div className="post-tags">
                    {post.tags.slice(0, 3).map((tag) => (
                      <span key={tag} className="tag">{tag}</span>
                    ))}
                  </div>
                  <span className="read-more">Read more →</span>
                </div>
              </div>
            </Link>
          </article>
        ))}
      </div>
    </div>
  );
};

export default BlogList;