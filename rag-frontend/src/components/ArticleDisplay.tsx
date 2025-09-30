import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { GenerateResponse } from '../services/api';
import { FiExternalLink, FiClock, FiCpu, FiBookOpen } from 'react-icons/fi';

interface ArticleDisplayProps {
  response: GenerateResponse | null;
  isLoading: boolean;
}

const ArticleDisplay: React.FC<ArticleDisplayProps> = ({ response, isLoading }) => {
  if (isLoading) {
    return (
      <div className="article-loading">
        <div className="loading-animation">
          <div className="pulse"></div>
          <p>Generating your article...</p>
          <p className="loading-subtext">This may take a few moments</p>
        </div>
      </div>
    );
  }

  if (!response) {
    return (
      <div className="article-placeholder">
        <h2>Your Generated Article Will Appear Here</h2>
        <p>Select topics and enter a query to generate custom content based on the blog posts.</p>
      </div>
    );
  }

  return (
    <div className="article-container">
      <div className="article-metadata">
        <div className="meta-item">
          <FiClock />
          <span>{(response.generation_time_ms / 1000).toFixed(2)}s</span>
        </div>
        <div className="meta-item">
          <FiCpu />
          <span>{response.model_used}</span>
        </div>
        <div className="meta-item">
          <FiBookOpen />
          <span>{response.chunks_retrieved} sources</span>
        </div>
      </div>

      <article className="generated-article">
        <ReactMarkdown
          components={{
            code({ className, children, ...props }: any) {
              const match = /language-(\w+)/.exec(className || '');
              const inline = !className || !match;
              return !inline ? (
                <SyntaxHighlighter
                  language={match![1]}
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
            h1: ({ children }) => <h1 className="article-h1">{children}</h1>,
            h2: ({ children }) => <h2 className="article-h2">{children}</h2>,
            h3: ({ children }) => <h3 className="article-h3">{children}</h3>,
            p: ({ children }) => <p className="article-paragraph">{children}</p>,
            ul: ({ children }) => <ul className="article-list">{children}</ul>,
            ol: ({ children }) => <ol className="article-list ordered">{children}</ol>,
            blockquote: ({ children }) => (
              <blockquote className="article-blockquote">{children}</blockquote>
            ),
          }}
        >
          {response.article}
        </ReactMarkdown>
      </article>

      {response.references.length > 0 && (
        <div className="references-section">
          <h3>References</h3>
          <div className="references-list">
            {response.references.map((ref, index) => (
              <div key={ref.chunk_id} className="reference-item">
                <span className="ref-number">[{index + 1}]</span>
                <div className="ref-content">
                  <div className="ref-title">{ref.post_title}</div>
                  {ref.section_heading && (
                    <div className="ref-section">→ {ref.section_heading}</div>
                  )}
                  <a
                    href={`/${ref.post_slug}.html${ref.url.split('#')[1] ? '#' + ref.url.split('#')[1] : ''}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ref-link"
                  >
                    View Source <FiExternalLink />
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ArticleDisplay;