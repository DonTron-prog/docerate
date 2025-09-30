import React, { useState, useEffect } from 'react';
import './App.css';
import TagCloudComponent from './components/TagCloud';
import QueryInput from './components/QueryInput';
import ArticleDisplay from './components/ArticleDisplay';
import api, { Tag, GenerateResponse } from './services/api';

function App() {
  const [tags, setTags] = useState<Tag[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState<GenerateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isHealthy, setIsHealthy] = useState(true);

  useEffect(() => {
    loadTags();
    checkHealth();
  }, []);

  const loadTags = async () => {
    try {
      const tagsData = await api.getTags();
      setTags(tagsData);
    } catch (err) {
      console.error('Failed to load tags:', err);
      setError('Failed to load tags. Please refresh the page.');
    }
  };

  const checkHealth = async () => {
    const healthy = await api.checkHealth();
    setIsHealthy(healthy);
    if (!healthy) {
      setError('Backend service is not available. Please ensure the API is running.');
    }
  };

  const handleTagClick = (tagName: string) => {
    if (tagName === '') {
      // Clear all tags
      setSelectedTags([]);
    } else if (selectedTags.includes(tagName)) {
      setSelectedTags(selectedTags.filter(t => t !== tagName));
    } else {
      setSelectedTags([...selectedTags, tagName]);
    }
  };

  const handleGenerate = async (
    query: string,
    context: string,
    maxTokens: number,
    temperature: number
  ) => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await api.generate({
        query,
        tags: selectedTags,
        context: context || undefined,
        max_tokens: maxTokens,
        temperature,
      });
      setResponse(result);
    } catch (err: any) {
      console.error('Generation failed:', err);
      setError(err.response?.data?.detail || 'Failed to generate content. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="app-header">
        <div className="header-content">
          <h1>McGillivray LAB - RAG Search</h1>
          <p className="subtitle">
            AI-powered content generation based on blog posts
          </p>
        </div>
        {!isHealthy && (
          <div className="health-warning">
            ⚠️ Backend service is offline. Please check the API connection.
          </div>
        )}
      </header>

      <main className="app-main">
        <div className="content-wrapper">
          <aside className="sidebar">
            <TagCloudComponent
              tags={tags}
              selectedTags={selectedTags}
              onTagClick={handleTagClick}
            />
          </aside>

          <section className="main-content">
            <QueryInput
              onSubmit={handleGenerate}
              isLoading={isLoading}
            />

            {error && (
              <div className="error-message">
                <p>❌ {error}</p>
              </div>
            )}

            <ArticleDisplay
              response={response}
              isLoading={isLoading}
            />
          </section>
        </div>
      </main>

      <footer className="app-footer">
        <p>
          Powered by RAG (Retrieval-Augmented Generation) |
          <a href="/docs" target="_blank" rel="noopener noreferrer"> API Docs</a> |
          <a href="https://github.com/yourusername/dontron_blog" target="_blank" rel="noopener noreferrer"> GitHub</a>
        </p>
      </footer>
    </div>
  );
}

export default App;