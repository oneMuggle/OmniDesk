import { useState, useRef, useEffect, useCallback } from 'react';
import { sendSmartChatStream, getSessions, createSession, deleteSession } from '../api/smartAssistantApi';
import ToolResult from '../components/ToolResult';
import MessageMarkdown from '../components/MessageMarkdown';
import ThinkContent from '../../../shared/components/ThinkContent';
import { Button, message as antMessage } from 'antd';
import { CopyOutlined, RedoOutlined, LikeOutlined, DislikeOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';
import './SmartChatPage.css';

const parseThinkContent = (content) => {
  if (!content) return { mainContent: '', thinkContent: '' };

  const thinkStart = content.indexOf('<thinking>');
  const thinkEnd = content.indexOf('</thinking>');

  if (thinkStart === -1 || thinkEnd === -1) {
    return { mainContent: content, thinkContent: '' };
  }

  const thinkContent = content.slice(thinkStart + 10, thinkEnd).trim();
  const mainContent = (content.slice(0, thinkStart) + content.slice(thinkEnd + 11)).trim();

  return { mainContent, thinkContent };
};

const MessageActions = ({ content, onFeedback, feedback }) => (
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
      className={`action-btn ${feedback === 'up' ? 'active' : ''}`}
    />
    <Button
      type="text"
      size="small"
      icon={<DislikeOutlined />}
      onClick={() => onFeedback?.('down')}
      className={`action-btn ${feedback === 'down' ? 'active' : ''}`}
    />
  </div>
);

MessageActions.propTypes = {
  content: PropTypes.string,
  onFeedback: PropTypes.func,
  feedback: PropTypes.string,
};

const SmartChatPage = () => {
  const [inputMessage, setInputMessage] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [streamingAnswer, setStreamingAnswer] = useState('');
  const [streamingMeta, setStreamingMeta] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [showSessionList, setShowSessionList] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingAnswer]);

  // 加载会话列表
  useEffect(() => {
    const loadSessions = async () => {
      try {
        const response = await getSessions();
        const data = response.data.results || response.data;
        setSessions(Array.isArray(data) ? data : []);
      } catch {
        // 静默失败
      }
    };
    loadSessions();
  }, []);

  const handleNewSession = useCallback(async () => {
    try {
      const response = await createSession('新会话');
      setSessions(prev => [response.data, ...prev]);
      setCurrentSessionId(response.data.id);
      setMessages([]);
    } catch {
      // 静默失败
    }
  }, []);

  const handleSwitchSession = useCallback((session) => {
    setCurrentSessionId(session.id);
    setShowSessionList(false);
    // 恢复历史消息
    const historyMessages = session.messages || [];
    setMessages(historyMessages.map(msg => ({
      role: msg.role,
      content: msg.content,
      intent: msg.intent,
      tool_used: msg.tool_used,
      tool_result: msg.tool_result,
      sources: msg.sources,
    })));
  }, []);

  const handleDeleteSession = useCallback(async (sessionId) => {
    try {
      await deleteSession(sessionId);
      setSessions(prev => prev.filter(s => s.id !== sessionId));
      if (currentSessionId === sessionId) {
        setCurrentSessionId(null);
        setMessages([]);
      }
    } catch {
      // 静默失败
    }
  }, [currentSessionId]);

  // 解析 SSE 数据行
  const parseSSE = useCallback((text) => {
    const lines = text.split('\n');
    const events = [];
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          events.push(JSON.parse(line.slice(6)));
        } catch {
          // 忽略解析失败
        }
      }
    }
    return events;
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = { role: 'user', content: inputMessage };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInputMessage('');
    setIsLoading(true);
    setStreamingAnswer('');
    setStreamingMeta(null);

    try {
      const stream = await sendSmartChatStream(inputMessage, currentSessionId);
      const reader = stream.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // 处理完整的 SSE 消息（以 \n\n 分隔）
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          const events = parseSSE(part);
          for (const event of events) {
            if (event.type === 'meta') {
              setStreamingMeta(event);
            } else if (event.type === 'chunk') {
              setStreamingAnswer(prev => prev + event.content);
            } else if (event.type === 'session') {
              if (!currentSessionId && event.conversation_id) {
                setCurrentSessionId(event.conversation_id);
                const resp = await getSessions();
                setSessions(resp.data || []);
              }
            }
          }
        }
      }
    } catch (error) {
      setStreamingAnswer(`[错误] ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // 当流式回答完成时，追加到消息列表
  useEffect(() => {
    if (!isLoading && streamingAnswer && messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg.role !== 'user') return;

      const assistantMessage = {
        role: 'assistant',
        content: streamingAnswer,
        intent: streamingMeta?.intent,
        tool_used: streamingMeta?.tool_used,
        tool_result: streamingMeta?.tool_result,
        sources: streamingMeta?.sources,
      };
      setMessages(prev => [...prev, assistantMessage]);
      setStreamingAnswer('');
      setStreamingMeta(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, streamingAnswer, streamingMeta]);

  // 处理消息反馈
  const handleFeedback = useCallback((msgIndex, type) => {
    setMessages(prev => prev.map((msg, i) =>
      i === msgIndex ? { ...msg, feedback: type } : msg
    ));
  }, []);

  // 重试最后一条消息
  const handleRetry = useCallback(async () => {
    if (messages.length < 2) return;
    const lastUserMsg = messages[messages.length - 2];
    if (lastUserMsg.role !== 'user') return;

    // 移除最后一条 AI 回复
    setMessages(prev => prev.slice(0, -1));
    setIsLoading(true);
    setStreamingAnswer('');
    setStreamingMeta(null);

    try {
      const stream = await sendSmartChatStream(lastUserMsg.content, currentSessionId);
      const reader = stream.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          const events = parseSSE(part);
          for (const event of events) {
            if (event.type === 'meta') {
              setStreamingMeta(event);
            } else if (event.type === 'chunk') {
              setStreamingAnswer(prev => prev + event.content);
            } else if (event.type === 'session') {
              if (!currentSessionId && event.conversation_id) {
                setCurrentSessionId(event.conversation_id);
                const resp = await getSessions();
                setSessions(resp.data || []);
              }
            }
          }
        }
      }
    } catch (error) {
      setStreamingAnswer(`[错误] ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  }, [messages, currentSessionId, parseSSE]);

  return (
    <div className="smart-chat-container">
      <div className="smart-chat-header">
        <h2>智能助手</h2>
        <div className="smart-chat-header-actions">
          <button
            className="session-toggle-btn"
            onClick={() => setShowSessionList(!showSessionList)}
          >
            {showSessionList ? '关闭' : '会话'}
          </button>
        </div>
      </div>

      {showSessionList && (
        <div className="session-list-panel">
          <button className="new-session-btn" onClick={handleNewSession}>
            + 新会话
          </button>
          <ul className="session-list">
            {sessions.map(session => (
              <li
                key={session.id}
                className={`session-item ${currentSessionId === session.id ? 'active' : ''}`}
                onClick={() => handleSwitchSession(session)}
              >
                <span className="session-title">{session.title}</span>
                <button
                  className="delete-session-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteSession(session.id);
                  }}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="smart-chat-messages">
        {messages.map((msg, index) => {
          const { mainContent, thinkContent } = parseThinkContent(msg.content);
          return (
            <div key={index} className={`message ${msg.role}`}>
              <div className="message-content">
                {msg.role === 'user' ? (
                  <div className="user-message-text">{mainContent}</div>
                ) : (
                  <>
                    <MessageMarkdown content={mainContent} />
                    {thinkContent && <ThinkContent content={thinkContent} />}
                  </>
                )}
              </div>
              {msg.tool_result && <ToolResult intent={msg.intent} result={msg.tool_result} sources={msg.sources} />}
              {msg.role === 'assistant' && (
                <MessageActions
                  content={msg.content}
                  feedback={msg.feedback}
                  onFeedback={(type) => handleFeedback(index, type)}
                />
              )}
              {index === messages.length - 1 && msg.role === 'assistant' && (
                <div className="message-retry">
                  <Button
                    type="text"
                    size="small"
                    icon={<RedoOutlined />}
                    onClick={handleRetry}
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
                <MessageMarkdown content={mainContent} />
                {thinkContent && <ThinkContent content={thinkContent} />}
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
      <form onSubmit={handleSubmit} className="smart-chat-input-form">
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          placeholder="问我任何问题，例如：明天谁值班？"
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading}>
          {isLoading ? '发送中...' : '发送'}
        </button>
      </form>
    </div>
  );
};

export default SmartChatPage;
