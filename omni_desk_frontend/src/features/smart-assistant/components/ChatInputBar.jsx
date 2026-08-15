import PropTypes from 'prop-types';
import FileAttachmentInput from '../../../shared/components/FileAttachmentInput';

/**
 * 输入表单:文本输入 + 附件 + 发送/取消(R3-D1 拆分)。
 * 自 SmartChatPage.jsx L684-708 逐字搬运,状态与 handler 由 useSmartChat 注入。
 */
const ChatInputBar = ({
  inputMessage,
  attachment,
  isLoading,
  onInputChange,
  onAttachmentChange,
  onSubmit,
  onStop,
}) => (
  <form onSubmit={onSubmit} className="smart-chat-input-form">
    <div className="smart-chat-input-row">
      <input
        type="text"
        value={inputMessage}
        onChange={(e) => onInputChange(e.target.value)}
        placeholder="问我任何问题，例如：明天谁值班？"
        disabled={isLoading}
      />
      <FileAttachmentInput
        value={attachment}
        onChange={onAttachmentChange}
        disabled={isLoading}
      />
    </div>
    {isLoading ? (
      <button type="button" onClick={onStop} className="stop-btn">
        取消
      </button>
    ) : (
      <button type="submit" disabled={!inputMessage.trim()}>
        发送
      </button>
    )}
  </form>
);

ChatInputBar.propTypes = {
  inputMessage: PropTypes.string,
  attachment: PropTypes.object,
  isLoading: PropTypes.bool,
  onInputChange: PropTypes.func.isRequired,
  onAttachmentChange: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
  onStop: PropTypes.func.isRequired,
};

export default ChatInputBar;
