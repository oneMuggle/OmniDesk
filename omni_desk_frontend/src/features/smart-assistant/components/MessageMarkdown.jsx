import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CopyToClipboard } from 'react-copy-to-clipboard';
import { Button, message as antMessage } from 'antd';
import { CopyOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';
import { useState } from 'react';

const MessageMarkdown = ({ content }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    setCopied(true);
    antMessage.success('已复制到剪贴板');
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="message-markdown">
      <div className="markdown-actions">
        <CopyToClipboard text={content}>
          <Button
            type="text"
            size="small"
            icon={<CopyOutlined />}
            onClick={handleCopy}
            className="copy-btn"
          >
            {copied ? '已复制' : '复制'}
          </Button>
        </CopyToClipboard>
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
