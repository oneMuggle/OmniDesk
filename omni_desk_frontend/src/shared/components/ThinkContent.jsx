import { useState } from 'react';
import PropTypes from 'prop-types';
import './ThinkContent.css';

const ThinkContent = ({ content = '', defaultExpanded = false }) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

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
    <div className={`think-container ${isExpanded ? 'expanded' : 'collapsed'}`}>
      <div
        className="think-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="think-icon">🤔</span>
        <span className="think-title">思考过程</span>
        <span className={`think-toggle ${isExpanded ? 'expanded' : ''}`}>
          ▼
        </span>
      </div>
      <div className={`think-content ${isExpanded ? 'show' : ''}`}>
        {renderContent()}
      </div>
    </div>
  );
};

ThinkContent.propTypes = {
  content: PropTypes.string,
  defaultExpanded: PropTypes.bool,
};

ThinkContent.defaultProps = {
  defaultExpanded: false,
};

export default ThinkContent;
