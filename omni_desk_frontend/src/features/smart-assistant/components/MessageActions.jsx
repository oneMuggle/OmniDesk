import PropTypes from 'prop-types';
import './MessageActions.css';

const MessageActions = ({ message, onCopy, onRegenerate, onDelete, onQuote }) => {
  const isAssistant = message?.role === 'assistant';
  const isUser = message?.role === 'user';

  return (
    <div className="message-actions">
      <button
        className="message-action-btn"
        title="复制"
        onClick={() => onCopy?.(message)}
      >
        复制
      </button>
      {isAssistant && (
        <button
          className="message-action-btn"
          title="重新生成"
          onClick={() => onRegenerate?.(message)}
        >
          重新生成
        </button>
      )}
      {(isUser || isAssistant) && (
        <button
          className="message-action-btn"
          title="引用回复"
          onClick={() => onQuote?.(message)}
        >
          引用
        </button>
      )}
      <button
        className="message-action-btn message-action-btn--delete"
        title="删除"
        onClick={() => onDelete?.(message)}
      >
        删除
      </button>
    </div>
  );
};

export default MessageActions;

MessageActions.propTypes = {
  message: PropTypes.shape({
    role: PropTypes.string,
    content: PropTypes.string,
  }),
  onCopy: PropTypes.func,
  onRegenerate: PropTypes.func,
  onDelete: PropTypes.func,
  onQuote: PropTypes.func,
};
