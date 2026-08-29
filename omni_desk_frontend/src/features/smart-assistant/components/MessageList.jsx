import { Button, Typography } from 'antd';
import { RedoOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';
import ThinkContent from '../../../shared/components/ThinkContent';
import ToolResult from './ToolResult';
import MessageFeedbackActions from './MessageFeedbackActions';
import ScenarioCollabCard from '../scenario/components/ScenarioCollabCard';
import { parseThinkContent } from '../utils/chatUtils';

/**
 * 消息列表:历史气泡 + 流式气泡 + loading + 自动滚动(R3-D1 拆分)。
 * 自 SmartChatPage.jsx L617-683 逐字搬运,反馈/重试 handler 由 useSmartChat 注入。
 *
 * 特殊消息类型:
 * - type='collab_card':智能助手多智能体协作卡片(剧本化推进),
 *   由 useSmartChat.sendMessage 在 query 命中业务场景关键词时注入。
 *   跳过标准 think/tool_result/feedback/retry 渲染,直接交给 ScenarioCollabCard。
 */
const MessageList = ({
  messages,
  streamingAnswer,
  streamingMeta,
  isLoading,
  messagesEndRef,
  onFeedback,
  onRetry,
}) => (
  <div className="smart-chat-messages">
    {messages.map((msg, index) => {
      if (msg.type === 'collab_card') {
        return (
          <div
            key={msg.id || `collab-${index}`}
            className="message assistant collab-card-msg"
          >
            <ScenarioCollabCard
              scenarioId={msg.scenarioId}
              userInput={msg.userInput}
            />
          </div>
        );
      }
      const { mainContent, thinkContent } = parseThinkContent(msg.content);
      return (
        <div key={index} className={`message ${msg.role}`}>
          <div className="message-content">
            {msg.role === 'user' ? (
              <div className="user-message-text">{mainContent}</div>
            ) : (
              <ThinkContent thinkContent={thinkContent} mainContent={mainContent} />
            )}
          </div>
          {msg.role === 'assistant' && msg.errorHint && (
            <Typography.Text
              type="secondary"
              data-testid="message-error-hint"
              style={{ display: 'block', marginTop: 4 }}
            >
              {msg.errorHint}
            </Typography.Text>
          )}
          {msg.tool_result && <ToolResult intent={msg.intent} result={msg.tool_result} sources={msg.sources} />}
          {/* 失败消息(带 errorHint)无归属日志,feedback 提交必然 404,故不渲染赞踩按钮 */}
          {msg.role === 'assistant' && !msg.errorHint && (
            <MessageFeedbackActions
              content={msg.content}
              feedback={msg.feedback}
              submitting={msg.feedbackSubmitting}
              onFeedback={(type) => onFeedback(index, type)}
            />
          )}
          {index === messages.length - 1 && msg.role === 'assistant' && (
            <div className="message-retry">
              <Button
                type="text"
                size="small"
                icon={<RedoOutlined />}
                onClick={onRetry}
                disabled={isLoading}
              >
                重新生成
              </Button>
            </div>
          )}
        </div>
      );
    })}
    {streamingAnswer && (() => {
      const { mainContent, thinkContent } = parseThinkContent(streamingAnswer);
      return (
        <div className="message assistant">
          <div className="message-content">
            <ThinkContent thinkContent={thinkContent} mainContent={mainContent} />
          </div>
          {streamingMeta?.tool_result && (
            <ToolResult
              intent={streamingMeta.intent}
              result={streamingMeta.tool_result}
              sources={streamingMeta.sources}
            />
          )}
        </div>
      );
    })()}
    {isLoading && !streamingAnswer && <div className="loading-indicator">思考中...</div>}
    <div ref={messagesEndRef} />
  </div>
);

MessageList.propTypes = {
  messages: PropTypes.array,
  streamingAnswer: PropTypes.string,
  streamingMeta: PropTypes.object,
  isLoading: PropTypes.bool,
  messagesEndRef: PropTypes.object,
  onFeedback: PropTypes.func.isRequired,
  onRetry: PropTypes.func.isRequired,
};

export default MessageList;
