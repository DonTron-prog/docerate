import React, { useState } from 'react';
import { FiSearch, FiSettings } from 'react-icons/fi';

interface QueryInputProps {
  onSubmit: (query: string, context: string, maxTokens: number, temperature: number) => void;
  isLoading: boolean;
}

const QueryInput: React.FC<QueryInputProps> = ({ onSubmit, isLoading }) => {
  const [query, setQuery] = useState('');
  const [context, setContext] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [maxTokens, setMaxTokens] = useState(1000);
  const [temperature, setTemperature] = useState(0.7);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSubmit(query, context, maxTokens, temperature);
    }
  };

  return (
    <div className="query-input-container">
      <form onSubmit={handleSubmit}>
        <div className="input-group">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a question about the content..."
            className="query-input"
            disabled={isLoading}
          />
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="settings-btn"
            title="Advanced settings"
          >
            <FiSettings />
          </button>
          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="submit-btn"
          >
            {isLoading ? (
              <span className="loading-spinner">⟳</span>
            ) : (
              <FiSearch />
            )}
            {isLoading ? 'Generating...' : 'Generate'}
          </button>
        </div>

        {showAdvanced && (
          <div className="advanced-settings">
            <div className="setting-group">
              <label htmlFor="context">Additional Context (optional):</label>
              <textarea
                id="context"
                value={context}
                onChange={(e) => setContext(e.target.value)}
                placeholder="Add specific requirements or focus areas..."
                rows={3}
                className="context-input"
              />
            </div>

            <div className="setting-row">
              <div className="setting-group">
                <label htmlFor="maxTokens">Max Tokens: {maxTokens}</label>
                <input
                  type="range"
                  id="maxTokens"
                  min="200"
                  max="4000"
                  step="100"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(Number(e.target.value))}
                />
              </div>

              <div className="setting-group">
                <label htmlFor="temperature">Temperature: {temperature.toFixed(1)}</label>
                <input
                  type="range"
                  id="temperature"
                  min="0"
                  max="1"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(Number(e.target.value))}
                />
              </div>
            </div>
          </div>
        )}
      </form>
    </div>
  );
};

export default QueryInput;