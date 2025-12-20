import React from 'react';
import PropTypes from 'prop-types';
import './ThinkContent.css';

const ThinkContent = ({ content = '' }) => {
  if (!content) return null;

  // 处理代码块和缩进
  const renderContent = () => {
    return content.split('\n').map((line, i) => {
      const trimmed = line.trim();
      const isCode = trimmed.startsWith('<') || trimmed.startsWith('>') || 
                    trimmed.startsWith('<') || trimmed.startsWith('>');
      
      return (
        <p key={i} className={isCode ? 'code-line' : ''}>
          {line}
        </p>
      );
    });
  };

  return (
    <div className="think-container">
      <div className="think-header">🤔 思考过程</div>
      <div className="think-content">
        {renderContent()}
      </div>
    </div>
  );
};

ThinkContent.propTypes = {
  content: PropTypes.string,
};


export default ThinkContent;
