import React, { useState } from 'react';
import { Tag } from '../services/api';

interface TagCloudProps {
  tags: Tag[];
  selectedTags: string[];
  onTagClick: (tag: string) => void;
}

const TagCloudComponent: React.FC<TagCloudProps> = ({ tags, selectedTags, onTagClick }) => {
  const [isCollapsed, setIsCollapsed] = useState(true);
  // Calculate font size based on count
  const maxCount = Math.max(...tags.map(t => t.count), 1);
  const minCount = Math.min(...tags.map(t => t.count), 1);
  const sizeRange = { min: 12, max: 28 };

  const calculateSize = (count: number) => {
    const normalized = (count - minCount) / (maxCount - minCount || 1);
    return sizeRange.min + normalized * (sizeRange.max - sizeRange.min);
  };

  return (
    <div className="tag-cloud-container" style={{
      backgroundColor: '#272822',
      borderRadius: '12px',
      padding: '1.5rem',
      boxShadow: '0 4px 6px rgba(0, 0, 0, 0.3)'
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        cursor: 'pointer',
        userSelect: 'none'
      }}
      onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div>
          <h3 style={{ margin: 0 }}>Select Topics to Filter Content</h3>
          {isCollapsed && selectedTags.length > 0 && (
            <p style={{
              margin: '4px 0 0 0',
              fontSize: '14px',
              color: '#66d9ef',
              fontWeight: '500'
            }}>
              {selectedTags.length} topic{selectedTags.length > 1 ? 's' : ''} selected
            </p>
          )}
        </div>
        <button
          style={{
            background: 'none',
            border: 'none',
            color: '#a6e22e',
            fontSize: '24px',
            cursor: 'pointer',
            padding: '0 8px',
            display: 'flex',
            alignItems: 'center',
            transition: 'transform 0.3s ease',
            transform: isCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)'
          }}
          aria-label={isCollapsed ? 'Expand' : 'Collapse'}
        >
          ▼
        </button>
      </div>

      <div style={{
        maxHeight: isCollapsed ? '0' : '1000px',
        overflow: 'hidden',
        transition: 'max-height 0.3s ease-in-out',
        opacity: isCollapsed ? 0 : 1,
        marginTop: isCollapsed ? '0' : '16px'
      }}>
        <div className="tag-cloud" style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '8px',
        padding: '16px',
        minHeight: '80px',
        alignItems: 'center',
        justifyContent: 'flex-start'
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
                backgroundColor: isSelected ? '#66d9ef' : '#3e3d32',
                color: isSelected ? '#272822' : '#a6e22e',
                border: isSelected ? '2px solid #66d9ef' : '2px solid #49483e',
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
                  e.currentTarget.style.backgroundColor = '#49483e';
                  e.currentTarget.style.transform = 'scale(1.05)';
                }
              }}
              onMouseOut={(e) => {
                if (!isSelected) {
                  e.currentTarget.style.backgroundColor = '#3e3d32';
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
          marginTop: '12px',
          padding: '8px 12px',
          backgroundColor: 'rgba(102, 217, 239, 0.1)',
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          border: '1px solid #3e3d32'
        }}>
          <p style={{ margin: 0, fontWeight: '500', color: '#66d9ef' }}>
            Selected tags: <span style={{ fontWeight: 'normal', color: '#f8f8f2' }}>{selectedTags.join(', ')}</span>
          </p>
          <button
            onClick={() => onTagClick('')}
            className="clear-btn"
            style={{
              padding: '4px 10px',
              backgroundColor: '#f92672',
              color: '#272822',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: '600',
              transition: 'background-color 0.2s',
              marginLeft: '12px'
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.backgroundColor = '#ff5a95';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.backgroundColor = '#f92672';
            }}
          >
            Clear All
          </button>
        </div>
      )}
      </div>
    </div>
  );
};

export default TagCloudComponent;