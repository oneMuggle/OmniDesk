import { useState } from 'react';
import { Collapse } from 'antd';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import PropTypes from 'prop-types';
import './ThinkContent.css';

/**
 * Think 内容展示组件。
 *
 * 支持两种 API:
 * - 新 API: thinkContent(思考内容) + mainContent(正文)
 * - 旧 API: content(仅思考内容,向后兼容 RagflowChatPage)
 *
 * Think 部分使用 Ant Design Collapse,默认折叠,💭 图标,浅灰色背景。
 */
const ThinkContent = ({
  thinkContent = '',
  mainContent = '',
  content = '',
  defaultExpanded = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  // 向后兼容:旧 API 使用 content 作为 thinkContent
  const effectiveThink = thinkContent || content;

  if (!effectiveThink && !mainContent) return null;

  const thinkHeader = (
    <span className="think-header-content">
      <span className="think-icon">💭</span>
      <span className="think-title">思考过程</span>
    </span>
  );

  // 无 think 内容时,仅渲染正文
  if (!effectiveThink) {
    return mainContent ? (
      <div className="think-main-only">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{mainContent}</ReactMarkdown>
      </div>
    ) : null;
  }

  return (
    <div className="think-wrapper">
      <Collapse
        ghost
        activeKey={isExpanded ? ['think'] : []}
        onChange={(keys) => setIsExpanded(keys.length > 0)}
        className="think-collapse"
      >
        <Collapse.Panel header={thinkHeader} key="think">
          <div className="think-body">
            {effectiveThink.split('\n').map((line, i) => (
              <p key={i} className={line.trim().startsWith('<') || line.trim().startsWith('>') ? 'code-line' : ''}>
                {line || ' '}
              </p>
            ))}
          </div>
        </Collapse.Panel>
      </Collapse>
      {mainContent && (
        <div className="think-main-content">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{mainContent}</ReactMarkdown>
        </div>
      )}
    </div>
  );
};

ThinkContent.propTypes = {
  /** 思考内容(新 API) */
  thinkContent: PropTypes.string,
  /** 正文内容(新 API,Markdown 格式) */
  mainContent: PropTypes.string,
  /** 思考内容(旧 API,向后兼容) */
  content: PropTypes.string,
  /** 是否默认展开(旧 API 遗留) */
  defaultExpanded: PropTypes.bool,
};

ThinkContent.defaultProps = {
  thinkContent: '',
  mainContent: '',
  content: '',
  defaultExpanded: false,
};

export default ThinkContent;
