import React from 'react';
import { Tag } from '../services/api';

interface TagCloudProps {
  tags: Tag[];
  selectedTags: string[];
  onTagClick: (tag: string) => void;
}

const TagCloudComponent: React.FC<TagCloudProps> = ({ tags, selectedTags, onTagClick }) => {
  // Calculate font size based on count
  const maxCount = Math.max(...tags.map(t => t.count), 1);
  const minCount = Math.min(...tags.map(t => t.count), 1);
  const sizeRange = { min: 12, max: 28 };

  const calculateSize = (count: number) => {
    const normalized = (count - minCount) / (maxCount - minCount || 1);
    return sizeRange.min + normalized * (sizeRange.max - sizeRange.min);
  };

  return (
    <div className="tag-cloud-container">
      <h3>Topics</h3>
      <div className="tag-cloud" style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '8px',
        padding: '16px',
        minHeight: '200px',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        {tags.map(tag => {
          const isSelected = selectedTags.includes(tag.name);
          const size = calculateSize(tag.count);

          return (
            <button
              key={tag.name}
              className={`tag-item ${isSelected ? 'selected' : ''}`}
              style={{
                cursor: 'pointer',
                padding: `${size / 4}px ${size / 2}px`,
                margin: '4px',
                borderRadius: '8px',
                display: 'inline-block',
                transition: 'all 0.3s ease',
                backgroundColor: isSelected ? '#3b82f6' : '#e5e7eb',
                color: isSelected ? 'white' : '#374151',
                border: isSelected ? '2px solid #2563eb' : '2px solid transparent',
                fontSize: `${size}px`,
                fontWeight: tag.count > 20 ? '600' : '400',
                fontFamily: 'inherit',
                lineHeight: 1.2,
                boxShadow: isSelected
                  ? '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                  : '0 1px 3px 0 rgba(0, 0, 0, 0.1)',
                transform: isSelected ? 'scale(1.05)' : 'scale(1)',
              }}
              onClick={() => onTagClick(tag.name)}
              onMouseOver={(e) => {
                if (!isSelected) {
                  e.currentTarget.style.backgroundColor = '#d1d5db';
                  e.currentTarget.style.transform = 'scale(1.05)';
                }
              }}
              onMouseOut={(e) => {
                if (!isSelected) {
                  e.currentTarget.style.backgroundColor = '#e5e7eb';
                  e.currentTarget.style.transform = 'scale(1)';
                }
              }}
            >
              {tag.name} ({tag.count})
            </button>
          );
        })}
      </div>

      {selectedTags.length > 0 && (
        <div className="selected-tags" style={{
          marginTop: '16px',
          padding: '12px',
          backgroundColor: '#f3f4f6',
          borderRadius: '8px'
        }}>
          <p style={{ marginBottom: '8px', fontWeight: '500' }}>
            Selected: {selectedTags.join(', ')}
          </p>
          <button
            onClick={() => onTagClick('')}
            className="clear-btn"
            style={{
              padding: '6px 12px',
              backgroundColor: '#ef4444',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
              transition: 'background-color 0.2s'
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.backgroundColor = '#dc2626';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.backgroundColor = '#ef4444';
            }}
          >
            Clear All
          </button>
        </div>
      )}
    </div>
  );
};

export default TagCloudComponent;