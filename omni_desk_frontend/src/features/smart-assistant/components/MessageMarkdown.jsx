import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Button, message as antMessage } from 'antd';
import { CopyOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';
import { useState } from 'react';
import copyToClipboard from '../../../shared/utils/clipboard';

const MessageMarkdown = ({ content }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    // R5-C2:原生剪贴板 API 替代 react-copy-to-clipboard
    const ok = await copyToClipboard(content);
    if (ok) {
      setCopied(true);
      antMessage.success('已复制到剪贴板');
      setTimeout(() => setCopied(false), 2000);
    } else {
      antMessage.error('复制失败,请手动选择文本复制');
    }
  };

  return (
    <div className="message-markdown">
      <div className="markdown-actions">
        <Button
          type="text"
          size="small"
          icon={<CopyOutlined />}
          onClick={handleCopy}
          className="copy-btn"
        >
          {copied ? '已复制' : '复制'}
        </Button>
      </div>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default MessageMarkdown;

MessageMarkdown.propTypes = {
  content: PropTypes.string,
};
