import { useState, useRef, useEffect, useCallback } from 'react';
import { sendSmartChatStream, getSessions, createSession, deleteSession } from '../api/smartAssistantApi';
import ToolResult from '../components/ToolResult';
import './SmartChatPage.css';

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
        setSessions(response.data || []);
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
  const parseSSE = (text) => {
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
  };

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
  }, [isLoading, streamingAnswer, streamingMeta]);

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
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.role}`}>
            <div className="message-content">
              {msg.content}
              {msg.tool_result && <ToolResult intent={msg.intent} result={msg.tool_result} sources={msg.sources} />}
            </div>
          </div>
        ))}
        {streamingAnswer && (
          <div className="message assistant">
            <div className="message-content">
              {streamingAnswer}
              {streamingMeta?.tool_result && (
                <ToolResult
                  intent={streamingMeta.intent}
                  result={streamingMeta.tool_result}
                  sources={streamingMeta.sources}
                />
              )}
            </div>
          </div>
        )}
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
