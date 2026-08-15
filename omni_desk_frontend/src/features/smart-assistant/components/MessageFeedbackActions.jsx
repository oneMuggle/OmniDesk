import { Button, message as antMessage } from 'antd';
import { CopyOutlined, LikeOutlined, DislikeOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';

/**
 * 助手消息操作栏:复制 / 赞 / 踩(R3-D1 拆分)。
 * 自 SmartChatPage.jsx 内联 MessageActions(L54-90)改名迁移,
 * 消解与旧版 components/MessageActions.jsx(复制/重新生成/引用/删除)的命名冲突。
 */
const MessageFeedbackActions = ({ content, onFeedback, feedback, submitting }) => (
  <div className="message-actions">
    <Button
      type="text"
      size="small"
      icon={<CopyOutlined />}
      onClick={() => {
        navigator.clipboard?.writeText(content);
        antMessage.success('已复制到剪贴板');
      }}
      className="action-btn"
    />
    <Button
      type="text"
      size="small"
      icon={<LikeOutlined />}
      onClick={() => onFeedback?.('up')}
      loading={submitting && feedback === 'up'}
      className={`action-btn ${feedback === 'up' ? 'active' : ''}`}
    />
    <Button
      type="text"
      size="small"
      icon={<DislikeOutlined />}
      onClick={() => onFeedback?.('down')}
      loading={submitting && feedback === 'down'}
      className={`action-btn ${feedback === 'down' ? 'active' : ''}`}
    />
  </div>
);

MessageFeedbackActions.propTypes = {
  content: PropTypes.string,
  onFeedback: PropTypes.func,
  feedback: PropTypes.oneOf(['up', 'down']),
  submitting: PropTypes.bool,
};

export default MessageFeedbackActions;
