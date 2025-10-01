import React, { useState, useEffect } from 'react';
import TagCloudComponent from '../components/TagCloud';
import QueryInput from '../components/QueryInput';
import ArticleDisplay from '../components/ArticleDisplay';
import api, { Tag, GenerateResponse } from '../services/api';

const AIExplorer: React.FC = () => {
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
    <div className="ai-explorer">
      {!isHealthy && (
        <div className="health-warning">
          ⚠️ Backend service is offline. Please check the API connection.
        </div>
      )}

      <div className="explorer-header">
        <h2>AI Content Explorer</h2>
        <p className="subtitle">
          Generate insights and summaries from blog content using AI
        </p>
      </div>

      <div className="main-container">
        <TagCloudComponent
          tags={tags}
          selectedTags={selectedTags}
          onTagClick={handleTagClick}
        />

        <QueryInput
          onSubmit={handleGenerate}
          isLoading={isLoading}
          selectedTagsCount={selectedTags.length}
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
      </div>
    </div>
  );
};

export default AIExplorer;