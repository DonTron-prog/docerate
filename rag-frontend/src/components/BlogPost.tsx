import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import { apiService } from '../services/api';
import './BlogPost.css';

interface PostDetail {
  slug: string;
  title: string;
  date: string;
  tags: string[];
  category: string;
  description: string;
  content: string;
  html_content: string;
  reading_time: number;
}

const BlogPost: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [post, setPost] = useState<PostDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPost = async () => {
      if (!slug) return;

      try {
        setLoading(true);
        const data = await apiService.getPost(slug);
        setPost(data);
      } catch (err) {
        setError('Failed to load blog post');
        console.error('Error fetching post:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPost();
  }, [slug]);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  const handleTagClick = (tag: string) => {
    navigate(`/blog?tag=${tag}`);
  };

  if (loading) {
    return (
      <div className="blog-post-container">
        <div className="loading">Loading post...</div>
      </div>
    );
  }

  if (error || !post) {
    return (
      <div className="blog-post-container">
        <div className="error">{error || 'Post not found'}</div>
        <Link to="/blog" className="back-link">← Back to blog</Link>
      </div>
    );
  }

  return (
    <div className="blog-post-container">
      <article className="blog-post">
        <header className="post-header">
          <Link to="/blog" className="back-link">← Back to blog</Link>

          <h1 className="post-title">{post.title}</h1>

          <div className="post-meta">
            <time className="post-date">{formatDate(post.date)}</time>
            <span className="post-reading-time">{post.reading_time} min read</span>
            <span className="post-category">{post.category}</span>
          </div>

          {post.description && (
            <p className="post-description">{post.description}</p>
          )}

          <div className="post-tags">
            {post.tags.map((tag) => (
              <button
                key={tag}
                className="tag-button"
                onClick={() => handleTagClick(tag)}
              >
                {tag}
              </button>
            ))}
          </div>
        </header>

        <div className="post-content">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ className, children, ...props }: any) {
                const match = /language-(\w+)/.exec(className || '');
                const inline = !className;
                return !inline && match ? (
                  <SyntaxHighlighter
                    language={match[1]}
                    style={vscDarkPlus as any}
                    PreTag="div"
                    {...props}
                  >
                    {String(children).replace(/\n$/, '')}
                  </SyntaxHighlighter>
                ) : (
                  <code className={className} {...props}>
                    {children}
                  </code>
                );
              },
              h1: ({ children }) => <h2 className="content-h2">{children}</h2>,
              h2: ({ children }) => <h3 className="content-h3">{children}</h3>,
              h3: ({ children }) => <h4 className="content-h4">{children}</h4>,
              a: ({ href, children }) => (
                <a href={href} target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              ),
            }}
          >
            {post.content}
          </ReactMarkdown>
        </div>

        <footer className="post-footer">
          <div className="post-nav">
            <Link to="/blog" className="nav-button">
              ← All Posts
            </Link>
          </div>
        </footer>
      </article>
    </div>
  );
};

export default BlogPost;