import { useState, useRef, useEffect, useCallback } from 'react';
import { sendSmartChatStream, sendSmartChat, getSessions, createSession, deleteSession, submitFeedback, resolveErrorHint } from '../api/smartAssistantApi';
import { forkSession, exportSessionMarkdown } from './sessionForkExportApi';
import { useTypewriter } from '../hooks/useTypewriter';
import ToolResult from '../components/ToolResult';
import ThinkContent from '../../../shared/components/ThinkContent';
import FileAttachmentInput from '../../../shared/components/FileAttachmentInput';
import { Button, Typography, Dropdown, Modal as AntdModal, message as antMessage } from 'antd';
import { CopyOutlined, RedoOutlined, LikeOutlined, DislikeOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';
import { logger } from '../../../shared/utils/logger';
import './SmartChatPage.css';

/**
 * 会话历史消息 → 页面展示消息（字段映射集中处理，
 * 复用于切换会话与 fork 后切入副本会话）。
 */
const toDisplayMessages = (historyMessages) =>
  (historyMessages || []).map(msg => ({
    role: msg.role,
    content: msg.content,
    intent: msg.intent,
    tool_used: msg.tool_used,
    tool_result: msg.tool_result,
    sources: msg.sources,
    // 兼容:旧版会话历史无 log_id 时为 undefined,反馈仅记本地
    logId: msg.log_id,
  }));

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

const MessageActions = ({ content, onFeedback, feedback, submitting }) => (
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

MessageActions.propTypes = {
  content: PropTypes.string,
  onFeedback: PropTypes.func,
  feedback: PropTypes.oneOf(['up', 'down']),
  submitting: PropTypes.bool,
};

/** 打字机节流间隔(ms) */
const TYPEWRITER_INTERVAL = 50;

const SmartChatPage = () => {
  const [inputMessage, setInputMessage] = useState('');
  const [attachment, setAttachment] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [streamingAnswer, setStreamingAnswer] = useState('');
  const [streamingMeta, setStreamingMeta] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [showSessionList, setShowSessionList] = useState(false);
  const messagesEndRef = useRef(null);
  const abortRef = useRef(null);
  // 当前流式响应携带的 AgentLog ID(done/session 等事件的 log_id 字段),
  // 流结束后附加到 assistant 消息上,用于赞踩反馈写后端
  const pendingLogIdRef = useRef(null);
  // 当前流式响应携带的失败辅助提示(输出契约 format_version:1,done/session
  // 事件的 kind/hint 字段);旧事件无字段时保持 null,不渲染提示行
  const pendingErrorHintRef = useRef(null);

  // 打字机 hook 适配:onTick 同步 ref → state,避免每次揭示都触发额外渲染
  const onTypewriterTick = useCallback(
    (displayed) => setStreamingAnswer(displayed),
    []
  );
  const typewriter = useTypewriter({
    onTick: onTypewriterTick,
    intervalMs: TYPEWRITER_INTERVAL,
  });

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
    setMessages(toDisplayMessages(session.messages));
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

  /** 创建副本（fork）：成功后切入新会话并展示其历史消息 */
  const handleForkSession = useCallback(async (session) => {
    try {
      const response = await forkSession(session.id);
      const newSession = response.data;
      setSessions(prev => [newSession, ...prev]);
      setCurrentSessionId(newSession.id);
      setShowSessionList(false);
      setMessages(toDisplayMessages(newSession.messages));
      antMessage.success('已创建会话副本');
    } catch {
      antMessage.error('创建副本失败，请稍后重试');
    }
  }, []);

  /** 导出 Markdown：fetch + blob 下载，失败统一提示 */
  const handleExportSession = useCallback(async (session) => {
    try {
      await exportSessionMarkdown(session.id, session.title);
      antMessage.success('导出成功');
    } catch {
      antMessage.error('导出失败，请稍后重试');
    }
  }, []);

  /** 会话操作菜单路由（fork / export） */
  const handleSessionMenuClick = useCallback((session, { key, domEvent }) => {
    domEvent.stopPropagation();
    if (key === 'fork') {
      handleForkSession(session);
    } else if (key === 'export') {
      handleExportSession(session);
    }
  }, [handleForkSession, handleExportSession]);

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

  // ── SSE 事件处理器 ──

  /** 处理 meta 事件:设置元数据,缓存命中时跳过打字机 */
  const handleMetaEvent = useCallback((event) => {
    setStreamingMeta(event);
    if (event.cache_hit) {
      typewriter.markCached();
    }
  }, [typewriter]);

  /** 处理 chunk 事件:累积文本,驱动打字机 */
  const handleChunkEvent = useCallback((event) => {
    typewriter.append(event.content);
  }, [typewriter]);

  /** 处理 session 事件:更新会话 ID */
  const handleSessionEvent = useCallback(async (event, activeSessionId) => {
    if (!activeSessionId && event.conversation_id) {
      setCurrentSessionId(event.conversation_id);
      // 会话列表后台刷新:不能 await,否则阻塞 runStream 读取循环,
      // reader.read() 的 done:true(连接关闭)被推迟 → setIsLoading(false)
      // 延迟 → 内容显示完整后按钮还卡在"取消"。fire-and-forget,
      // 列表稍晚更新对用户无感。
      getSessions()
        .then((resp) => {
          // 与 loadSessions 一致:解包 DRF 分页 {results},防御非数组
          const data = resp.data?.results || resp.data;
          setSessions(Array.isArray(data) ? data : []);
        })
        .catch(() => {
          // 静默:列表刷新失败不影响本次对话收尾
        });
      return event.conversation_id;
    }
    return activeSessionId;
  }, []);

  /**
   * 处理 SSE confirmation 事件:弹出确认对话框,用户确认后
   * 二次请求 sendSmartChat(inputMessage, currentSessionId, null, token)
   * (非流式,后端 Task 8 已支持 confirm_token replay),把响应里的
   * tool_result.file_download 推入 messages(由 ToolResult 渲染下载卡片)。
   */
  const handleConfirmation = useCallback(async (event) => {
    const token = event.confirmation_token;
    const draft = event.draft || {};
    if (!token) return;
    AntdModal.confirm({
      title: '请确认操作',
      content: event.answer || draft.summary || '确认执行该操作吗?',
      okText: '确认生成',
      cancelText: '取消',
      onOk: async () => {
        try {
          const resp = await sendSmartChat(inputMessage, currentSessionId, null, token);
          const data = resp.data;
          if (data && data.tool_result && data.tool_result.file_download) {
            setMessages((prev) => [
              ...prev,
              {
                id: Date.now(),
                role: 'assistant',
                intent: data.tool_used,
                content: data.answer || '文档已生成',
                tool_result: data.tool_result,
                sources: null,
              },
            ]);
          }
        } catch (err) {
          antMessage.error(err.message || '确认执行失败');
        }
      },
    });
  }, [inputMessage, currentSessionId]);

  /** 处理单个 SSE 事件,路由到对应的处理器 */
  const handleSSEEvent = useCallback(async (event, activeSessionId) => {
    // 兼容旧版事件:无 log_id 字段时静默跳过
    if (event.log_id !== undefined && event.log_id !== null) {
      pendingLogIdRef.current = event.log_id;
    }
    // 输出契约(format_version:1):失败时 done/session 事件携带 kind/hint。
    // 旧事件无这些字段 → resolveErrorHint 返回 undefined,行为与旧版一致。
    if (event.type === 'done' || event.type === 'session') {
      const errorHint = resolveErrorHint(event);
      if (errorHint) {
        pendingErrorHintRef.current = errorHint;
        // 失败但流未产出任何正文时,兜底一条失败气泡,保证提示行有载体
        // (走 typewriter.append 由 onTick → setStreamingAnswer 显示)。
        // 必须用 typewriter.getReceived() 而非 streamingAnswer:
        // receivedTextRef 是 hook 内部同步累积缓冲(append 内 +=,立即可读);
        // streamingAnswer 是 React state,onTick 触发 setStreamingAnswer 是异步批处理。
        // 当 SSE 流是 chunk+done 同轮到达时(例如 chunk:'回答生成失败' + done:{error}),
        // append 同步更新 receivedTextRef,但 setStreamingAnswer 尚未生效,此时
        // streamingAnswer 仍是空字符串 → 误判"流未产出正文" → 又 append 一次,
        // UI 中"回答生成失败"出现两次。getReceived 同步可读,避免这个竞态。
        if (event.type === 'done' && !typewriter.getReceived()) {
          typewriter.append('回答生成失败');
        }
      }
    }
    switch (event.type) {
      case 'meta':
        handleMetaEvent(event);
        break;
      case 'chunk':
        handleChunkEvent(event);
        break;
      case 'done':
        // 流结束标记由 runStream finally 统一设置 markStreamingEnd,
        // 这里不再直接维护 isStreamingRef(已迁移至 hook 内部)
        break;
      case 'session':
        return await handleSessionEvent(event, activeSessionId);
      case 'confirmation':
        await handleConfirmation(event);
        break;
      default:
        // 忽略未知事件类型
        break;
    }
    return activeSessionId;
  }, [handleMetaEvent, handleChunkEvent, handleSessionEvent, handleConfirmation, typewriter]);

  /**
   * 核心流式处理:读取 SSE reader,驱动打字机显示。
   * 被 handleSubmit 和 handleRetry 共用。
   *
   * 兜底超时:若后端 generator 因 DB 异常等原因未发 done 事件,前端
   * reader.read() 永远 pending。包一层 Promise.race,超时后调用 abort
   * 并 reject,让 handleSubmit 走到 catch + finally,isLoading 复位。
   *
   * 收尾顺序:流结束后若 typewriter 仍在渐进显示,先等它显示完整再
   * resolve。这样 handleSubmit 的 setIsLoading(false) 不会早于内容显示
   * 完整,useEffect 推入消息列表的 streamingAnswer 始终是完整内容。
   */
  const runStream = useCallback(async (query) => {
    pendingLogIdRef.current = null;
    pendingErrorHintRef.current = null;
    const { bodyPromise, abort } = sendSmartChatStream(query, currentSessionId, attachment);
    abortRef.current = abort;
    const stream = await bodyPromise;

    if (!stream) {
      return;
    }

    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    typewriter.beginStreaming();
    let activeSessionId = currentSessionId;

    // 超时兜底:60 秒未收到下一个 chunk 视为流卡死,abort 退出。
    // 由 catch (AbortError) 静默处理;handleSubmit finally 仍会 setIsLoading(false)。
    const STREAM_TIMEOUT_MS = 60_000;
    let timeoutId = null;
    const resetTimeout = () => {
      if (timeoutId) clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        logger.warn('[SmartChat] runStream timeout, aborting');
        if (abortRef.current) abortRef.current();
      }, STREAM_TIMEOUT_MS);
    };

    try {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        resetTimeout();
        const readPromise = reader.read();
        // 主动 timeout 不会触发 readPromise reject,只在 abort 时 reject;
        // 此处不 race,只用 resetTimeout 推进超时重置
        const { done, value } = await readPromise;
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          const events = parseSSE(part);
          for (const event of events) {
            activeSessionId = await handleSSEEvent(event, activeSessionId);
          }
        }
      }
    } finally {
      if (timeoutId) clearTimeout(timeoutId);
      // 先清 isStreaming,让 typewriter tick 在下一帧自然触发 complete;
      // 否则 displayedLen>=received.length && isStreaming=true 路径只排下个 rAF,
      // 不调 completeCallbacks,而 markStreamingEnd 又在 await 之后,死锁。
      typewriter.markStreamingEnd();
      if (typewriter.isComplete()) {
        typewriter.flush();
      } else {
        // typewriter 仍在渐进显示:等 hook 触发 onComplete 后再结束,
        // 保证 setIsLoading(false) 晚于内容显示完整,useEffect 不会把
        // 部分 streamingAnswer 推入消息列表。
        await new Promise((resolve) => typewriter.onComplete(resolve));
      }
    }
  }, [currentSessionId, attachment, parseSSE, handleSSEEvent, typewriter]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = { role: 'user', content: inputMessage, attachment: attachment ? attachment.name : null };
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setAttachment(null);
    setIsLoading(true);
    setStreamingAnswer('');
    setStreamingMeta(null);
    typewriter.cancel();

    try {
      await runStream(inputMessage);
    } catch (error) {
      if (error.name !== 'AbortError') {
        const errText = `[错误] ${error.message}`;
        typewriter.append(errText);
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
        logId: pendingLogIdRef.current,
        // 失败辅助提示(输出契约);旧事件无 kind/hint 时为 null,不渲染提示行
        errorHint: pendingErrorHintRef.current,
      };
      setMessages(prev => [...prev, assistantMessage]);
      setStreamingAnswer('');
      setStreamingMeta(null);
      pendingLogIdRef.current = null;
      pendingErrorHintRef.current = null;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, streamingAnswer, streamingMeta]);

  // 处理消息反馈(赞/踩):乐观更新本地状态并写后端,失败时回滚并提示
  const handleFeedback = useCallback(async (msgIndex, type) => {
    const msg = messages[msgIndex];
    if (!msg || msg.role !== 'assistant' || msg.feedbackSubmitting) return;
    // 防重复提交:相同反馈不重复调用 API(允许 up/down 互相改选)
    if (msg.feedback === type) return;

    // 无 logId 的历史消息(旧版事件未携带)仅记录本地状态
    if (!msg.logId) {
      setMessages(prev => prev.map((m, i) =>
        i === msgIndex ? { ...m, feedback: type } : m
      ));
      return;
    }

    const prevFeedback = msg.feedback ?? null;
    setMessages(prev => prev.map((m, i) =>
      i === msgIndex ? { ...m, feedback: type, feedbackSubmitting: true } : m
    ));
    try {
      await submitFeedback(msg.logId, type);
    } catch {
      // API 失败 → 回滚到提交前的反馈状态
      setMessages(prev => prev.map((m, i) =>
        i === msgIndex ? { ...m, feedback: prevFeedback } : m
      ));
      antMessage.error('反馈提交失败,请稍后重试');
    } finally {
      setMessages(prev => prev.map((m, i) =>
        i === msgIndex ? { ...m, feedbackSubmitting: false } : m
      ));
    }
  }, [messages]);

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
    typewriter.cancel();

    try {
      await runStream(lastUserMsg.content);
    } catch (error) {
      if (error.name !== 'AbortError') {
        const errText = `[错误] ${error.message}`;
        typewriter.append(errText);
      }
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  }, [messages, runStream, typewriter]);

  /** 停止生成:中止请求 + 清理打字机状态 + 显示提示 */
  const handleStop = useCallback(() => {
    if (abortRef.current) {
      abortRef.current();
      abortRef.current = null;
    }
    typewriter.cancel();
    setStreamingAnswer('');
    setStreamingMeta(null);
    setIsLoading(false);
    antMessage.info('已取消生成');
  }, [typewriter]);

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
                <Dropdown
                  menu={{
                    items: [
                      { key: 'fork', label: '创建副本' },
                      { key: 'export', label: '导出 Markdown' },
                    ],
                    onClick: (info) => handleSessionMenuClick(session, info),
                  }}
                  trigger={['click']}
                >
                  <button
                    className="session-menu-btn"
                    aria-label="会话操作"
                    onClick={(e) => e.stopPropagation()}
                  >
                    ⋯
                  </button>
                </Dropdown>
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
                <MessageActions
                  content={msg.content}
                  feedback={msg.feedback}
                  submitting={msg.feedbackSubmitting}
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
        <div className="smart-chat-input-row">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="问我任何问题，例如：明天谁值班？"
            disabled={isLoading}
          />
          <FileAttachmentInput
            value={attachment}
            onChange={setAttachment}
            disabled={isLoading}
          />
        </div>
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
