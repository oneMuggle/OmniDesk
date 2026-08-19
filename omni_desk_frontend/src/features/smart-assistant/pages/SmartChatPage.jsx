import { useSmartChat } from '../hooks/useSmartChat';
import ChatHeader from '../components/ChatHeader';
import SessionListPanel from '../components/SessionListPanel';
import MessageList from '../components/MessageList';
import ChatInputBar from '../components/ChatInputBar';
import './SmartChatPage.css';

/**
 * 智能助手聊天页(R3-D1 拆分后薄壳)。
 * 全部业务逻辑迁至 hooks/useSmartChat.js,渲染拆为 4 个子组件:
 * ChatHeader / SessionListPanel / MessageList / ChatInputBar。
 * 对外契约零变化:默认导出与 routes/index.jsx lazy import 路径不变。
 */
const SmartChatPage = () => {
  const {
    inputMessage, setInputMessage,
    attachment, setAttachment,
    messages, isLoading, streamingAnswer, streamingMeta,
    sessions, currentSessionId, showSessionList, setShowSessionList,
    messagesEndRef,
    handleNewSession, handleSwitchSession, handleDeleteSession,
    handleSessionMenuClick,
    handleSubmit, handleStop, handleRetry, handleFeedback,
  } = useSmartChat();

  return (
    <div className="smart-chat-container">
      <ChatHeader
        showSessionList={showSessionList}
        onToggleSessionList={() => setShowSessionList(!showSessionList)}
      />

      {showSessionList && (
        <SessionListPanel
          sessions={sessions}
          currentSessionId={currentSessionId}
          onNewSession={handleNewSession}
          onSwitchSession={handleSwitchSession}
          onDeleteSession={handleDeleteSession}
          onMenuClick={handleSessionMenuClick}
        />
      )}

      <MessageList
        messages={messages}
        streamingAnswer={streamingAnswer}
        streamingMeta={streamingMeta}
        isLoading={isLoading}
        messagesEndRef={messagesEndRef}
        onFeedback={handleFeedback}
        onRetry={handleRetry}
      />

      <ChatInputBar
        inputMessage={inputMessage}
        attachment={attachment}
        isLoading={isLoading}
        onInputChange={setInputMessage}
        onAttachmentChange={setAttachment}
        onSubmit={handleSubmit}
        onStop={handleStop}
      />
    </div>
  );
};

export default SmartChatPage;
