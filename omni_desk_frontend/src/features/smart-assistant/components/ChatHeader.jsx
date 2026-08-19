import PropTypes from 'prop-types';

/**
 * 智能助手页头:标题 + 会话列表切换按钮(R3-D1 拆分)。
 * 自 SmartChatPage.jsx L559-569 逐字搬运。
 */
const ChatHeader = ({ showSessionList, onToggleSessionList }) => (
  <div className="smart-chat-header">
    <h2>智能助手</h2>
    <div className="smart-chat-header-actions">
      <button
        className="session-toggle-btn"
        onClick={onToggleSessionList}
      >
        {showSessionList ? '关闭' : '会话'}
      </button>
    </div>
  </div>
);

ChatHeader.propTypes = {
  showSessionList: PropTypes.bool,
  onToggleSessionList: PropTypes.func.isRequired,
};

export default ChatHeader;
