import { useState, useRef, useEffect, useCallback } from 'react';
import { sendSmartChatStream, getSessions, createSession, deleteSession } from '../api/smartAssistantApi';
import ToolResult from '../components/ToolResult';
import ThinkContent from '../../../shared/components/ThinkContent';
import { Button, message as antMessage } from 'antd';
import { CopyOutlined, RedoOutlined, LikeOutlined, DislikeOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';
import './SmartChatPage.css';

/**
 * 解析内容中的 <thinking> 标签,分离思考内容与正文。
 * 支持多个 <thinking> 块(合并为一个 thinkContent)。
 */
const parseThinkContent = (content) => {
  if (!content) return { mainContent: '', thinkContent: '' };

  const thinkRegex = /<thinking>([\s\S]*?)<\/thinking>/g;
  const thinkParts = [];
  let match;

  while ((match = thinkRegex.exec(content)) !== null) {
    const trimmed = match[1].trim();
    if (trimmed) thinkParts.push(trimmed);
  }

  if (thinkParts.length === 0) {
    return { mainContent: content, thinkContent: '' };
  }

  const mainContent = content.replace(/<thinking>[\s\S]*?<\/thinking>/g, '').trim();
  return { mainContent, thinkContent: thinkParts.join('\n\n') };
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

/** 打字机节流间隔(ms) */
const TYPEWRITER_INTERVAL = 50;

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
  const abortRef = useRef(null);

  // ── 打字机效果 refs ──
  // receivedTextRef: 从 SSE 接收到的完整文本(chunks 缓冲)
  // displayedLenRef: 已经显示给用户的字符数
  // rafRef / lastTickRef: requestAnimationFrame 句柄与上次刷新时间戳
  // isCachedRef: 后端缓存命中标志(跳过打字机)
  // isStreamingRef: 流是否仍在接收数据
  const receivedTextRef = useRef('');
  const displayedLenRef = useRef(0);
  const rafRef = useRef(null);
  const lastTickRef = useRef(0);
  const isCachedRef = useRef(false);
  const isStreamingRef = useRef(false);

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

  // 组件卸载时清理 rAF
  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
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

  // ── 打字机效果核心函数 ──

  /** rAF 回调:每 TYPEWRITER_INTERVAL ms 逐步揭示已接收的文本 */
  const typewriterTick = useCallback(() => {
    const received = receivedTextRef.current;
    const displayedLen = displayedLenRef.current;

    if (displayedLen >= received.length) {
      if (!isStreamingRef.current) {
        // 流已结束且全部显示 → 停止 rAF 循环
        rafRef.current = null;
        return;
      }
      // 流仍在接收,等待更多数据
      rafRef.current = requestAnimationFrame(typewriterTick);
      return;
    }

    const now = performance.now();
    if (now - lastTickRef.current >= TYPEWRITER_INTERVAL) {
      const remaining = received.length - displayedLen;
      // 渐进揭示:剩余越多一次揭示越多,但上限 10 字符/帧
      const charsToAdd = Math.max(1, Math.min(Math.ceil(remaining * 0.2), 10));
      const newLen = Math.min(displayedLen + charsToAdd, received.length);

      setStreamingAnswer(received.slice(0, newLen));
      displayedLenRef.current = newLen;
      lastTickRef.current = now;
    }

    rafRef.current = requestAnimationFrame(typewriterTick);
  }, []);

  /** 重置打字机状态(新请求 / 取消时调用) */
  const resetTypewriter = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    receivedTextRef.current = '';
    displayedLenRef.current = 0;
    isCachedRef.current = false;
    isStreamingRef.current = false;
  }, []);

  /** 立即显示所有已接收文本(流结束兜底) */
  const flushTypewriter = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    const received = receivedTextRef.current;
    if (displayedLenRef.current < received.length) {
      setStreamingAnswer(received);
      displayedLenRef.current = received.length;
    }
  }, []);

  // ── SSE 解析 ──

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

  /**
   * 核心流式处理:读取 SSE reader,驱动打字机显示。
   * 被 handleSubmit 和 handleRetry 共用。
   */
  const runStream = useCallback(async (query) => {
    const { bodyPromise, abort } = sendSmartChatStream(query, currentSessionId);
    abortRef.current = abort;
    const stream = await bodyPromise;

    if (!stream) {
      // 用户取消或连接失败
      return;
    }

    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    isStreamingRef.current = true;
    let activeSessionId = currentSessionId;

    try {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // 处理完整的 SSE 消息(以 \n\n 分隔)
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          const events = parseSSE(part);
          for (const event of events) {
            if (event.type === 'meta') {
              setStreamingMeta(event);
              if (event.cache_hit) {
                // 缓存命中:跳过打字机,直接显示完整内容
                isCachedRef.current = true;
                setStreamingAnswer(receivedTextRef.current);
                displayedLenRef.current = receivedTextRef.current.length;
              }
            } else if (event.type === 'chunk') {
              receivedTextRef.current += event.content;
              if (isCachedRef.current) {
                // 缓存路径:直接显示
                setStreamingAnswer(receivedTextRef.current);
                displayedLenRef.current = receivedTextRef.current.length;
              } else if (!rafRef.current) {
                // 启动打字机
                lastTickRef.current = performance.now();
                rafRef.current = requestAnimationFrame(typewriterTick);
              }
            } else if (event.type === 'done') {
              isStreamingRef.current = false;
            } else if (event.type === 'session') {
              if (!activeSessionId && event.conversation_id) {
                activeSessionId = event.conversation_id;
                setCurrentSessionId(activeSessionId);
                const resp = await getSessions();
                setSessions(resp.data || []);
              }
            }
          }
        }
      }
    } finally {
      isStreamingRef.current = false;
      // 流结束:若打字机未运行,立即刷新剩余文本;
      // 若正在运行,typewriterTick 会自行检测 isStreaming=false 并完成
      if (!rafRef.current) {
        flushTypewriter();
      }
    }
  }, [currentSessionId, parseSSE, typewriterTick, flushTypewriter]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = { role: 'user', content: inputMessage };
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    setStreamingAnswer('');
    setStreamingMeta(null);
    resetTypewriter();

    try {
      await runStream(inputMessage);
    } catch (error) {
      if (error.name !== 'AbortError') {
        const errText = `[错误] ${error.message}`;
        receivedTextRef.current = errText;
        setStreamingAnswer(errText);
        displayedLenRef.current = errText.length;
      }
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  };

  // 当流式回答完成时,追加到消息列表
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
    resetTypewriter();

    try {
      await runStream(lastUserMsg.content);
    } catch (error) {
      if (error.name !== 'AbortError') {
        const errText = `[错误] ${error.message}`;
        receivedTextRef.current = errText;
        setStreamingAnswer(errText);
        displayedLenRef.current = errText.length;
      }
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  }, [messages, runStream, resetTypewriter]);

  /** 停止生成:中止请求 + 清理打字机状态 + 显示提示 */
  const handleStop = useCallback(() => {
    if (abortRef.current) {
      abortRef.current();
      abortRef.current = null;
    }
    isStreamingRef.current = false;
    resetTypewriter();
    setStreamingAnswer('');
    setStreamingMeta(null);
    setIsLoading(false);
    antMessage.info('已取消生成');
  }, [resetTypewriter]);

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
                  <ThinkContent thinkContent={thinkContent} mainContent={mainContent} />
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
      <form onSubmit={handleSubmit} className="smart-chat-input-form">
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          placeholder="问我任何问题，例如：明天谁值班？"
          disabled={isLoading}
        />
        {isLoading ? (
          <button type="button" onClick={handleStop} className="stop-btn">
            取消
          </button>
        ) : (
          <button type="submit" disabled={!inputMessage.trim()}>
            发送
          </button>
        )}
      </form>
    </div>
  );
};

export default SmartChatPage;
