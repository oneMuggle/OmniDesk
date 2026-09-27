import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { FloatButton, Drawer, Input, Button, Spin, Tag, Typography } from 'antd';
import { RobotOutlined, SendOutlined, FullscreenOutlined, CloseOutlined, StopOutlined, EyeOutlined } from '@ant-design/icons';
import {
  sendSmartChatStream,
  createSession,
  resolveErrorHint,
  getAssistantContext,
} from '../../features/smart-assistant/api/smartAssistantApi';
import { consumeSSEStream } from '../../features/smart-assistant/utils/chatUtils';
import { startAgentTask } from '../../features/smart-assistant/utils/startAgentTask';
import ToolResult from '../../features/smart-assistant/components/ToolResult';
import TaskProposalCard from '../../features/smart-assistant/components/TaskProposalCard';
import WriteConfirmCard, { toConfirmMessage } from '../../features/smart-assistant/components/WriteConfirmCard';
import FileAttachmentInput from './FileAttachmentInput';
import { useLocation, useNavigate } from 'react-router-dom';
import { AI_DRAWER_EVENT } from '../utils/aiDrawer';
import './QuickAssistant.css';

// 协作卡片只在创建多 Agent 任务后才需要,按需加载,不进主包
const ScenarioCollabCard = lazy(() => import('../../features/smart-assistant/scenario/components/ScenarioCollabCard'));

const { TextArea } = Input;

/** 完整智能助手页:该页自带对话,不再显示悬浮助手 */
// 智能助手完整页(含 S2-2 的任务 / 应用标签)上不显示悬浮按钮,避免同屏两个助手
const FULL_PAGE_ROUTE = '/smart-assistant';
const isFullAssistantPage = (pathname) =>
  pathname === FULL_PAGE_ROUTE || pathname.startsWith(`${FULL_PAGE_ROUTE}/`);

const EMPTY_CONTEXT = { pageContext: null, quickPrompts: [] };

/**
 * 全局 AI 抽屉(S2)。
 *
 * - 发送时带上当前页面路径(page_route),后端按权限重读当前记录作为上下文;
 * - 打开时按路由拉取「正在查看」标签与快捷问题(由各模块 ai_tools.py 声明);
 * - 其他页面可调用 openAIDrawer({ query }) 打开并自动发送问题;
 * - complex_task 返回任务计划卡,可在抽屉内创建多 Agent 协作任务并查看进度。
 */
const QuickAssistant = () => {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [attachment, setAttachment] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [streamingAnswer, setStreamingAnswer] = useState('');
  const [streamingMeta, setStreamingMeta] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [assistantContext, setAssistantContext] = useState(EMPTY_CONTEXT);
  const messagesEndRef = useRef(null);
  const abortRef = useRef(null);
  // 始终指向最新一次渲染的 sendQuery,供 window 事件回调(只注册一次)调用
  const sendQueryRef = useRef(null);
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingAnswer]);

  // 打开抽屉 / 切换页面时拉取页面上下文与快捷问题;失败时静默降级为空
  useEffect(() => {
    if (!open) return undefined;
    let cancelled = false;
    getAssistantContext(pathname)
      .then((resp) => {
        if (cancelled) return;
        const data = resp?.data || {};
        setAssistantContext({
          pageContext: data.page_context || null,
          quickPrompts: Array.isArray(data.quick_prompts) ? data.quick_prompts : [],
        });
      })
      .catch(() => {
        if (!cancelled) setAssistantContext(EMPTY_CONTEXT);
      });
    return () => {
      cancelled = true;
    };
  }, [open, pathname]);

  // 全局唤起:openAIDrawer({ query });正在回答时不打断,把问题放进输入框
  useEffect(() => {
    const handleOpenEvent = (event) => {
      setOpen(true);
      const query = event?.detail?.query;
      if (!query) return;
      const accepted = sendQueryRef.current ? sendQueryRef.current(query) : false;
      if (!accepted) setInputMessage(query);
    };
    window.addEventListener(AI_DRAWER_EVENT, handleOpenEvent);
    return () => window.removeEventListener(AI_DRAWER_EVENT, handleOpenEvent);
  }, []);

  const ensureSession = async () => {
    if (sessionId) return sessionId;
    try {
      const resp = await createSession('快捷会话');
      const newId = resp.data.id;
      setSessionId(newId);
      return newId;
    } catch {
      return null;
    }
  };

  /**
   * 执行一次流式问答。流结束后直接用本地累积的正文 / 元数据落一条 assistant 消息,
   * 不再依赖"isLoading 变化后在 effect 里补消息"的写法。
   */
  const runQuery = async (query, options = {}) => {
    const currentSessionId = await ensureSession();
    if (!currentSessionId) return;

    const userMessage = { role: 'user', content: query, attachment: attachment ? attachment.name : null };
    setMessages(prev => [...prev, userMessage]);
    const currentAttachment = attachment;
    setInputMessage('');
    setAttachment(null);
    setIsLoading(true);
    setStreamingAnswer('');
    setStreamingMeta(null);

    let answer = '';
    let meta = null;
    // 失败辅助提示(输出契约 format_version:1,done/session 事件的 kind/hint);
    // 旧事件无字段时保持 null,不渲染提示行
    let errorHint = null;
    // 写操作确认卡(confirmation 事件),流结束后追加在回答之后
    let confirmMessage = null;

    try {
      const { bodyPromise, abort } = sendSmartChatStream(query, currentSessionId, currentAttachment, null, {
        pageRoute: pathname,
        skipTaskProposal: Boolean(options.skipTaskProposal),
      });
      abortRef.current = abort;
      const stream = await bodyPromise;

      if (!stream) {
        // 用户取消或连接失败
        return;
      }

      // R4-B2:SSE 读取骨架收敛到共享 consumeSSEStream(chatUtils.js)
      await consumeSSEStream(stream, (event) => {
        if (event.type === 'meta') {
          meta = event;
          setStreamingMeta(event);
        } else if (event.type === 'chunk') {
          answer += event.content;
          setStreamingAnswer(answer);
        } else if (event.type === 'confirmation') {
          // 写操作确认卡:卡片自己调用确认 / 取消 / 撤销接口
          confirmMessage = toConfirmMessage(event, meta?.tool_used);
        } else if (event.type === 'done' || event.type === 'session') {
          // 旧事件无 kind/hint 字段 → resolveErrorHint 返回 undefined,行为与旧版一致
          const hint = resolveErrorHint(event);
          if (hint) {
            errorHint = hint;
            // 失败但流未产出任何正文时,兜底一条失败气泡,保证提示行有载体
            if (event.type === 'done' && !answer) {
              answer = '回答生成失败';
              setStreamingAnswer(answer);
            }
          }
        }
      });
    } catch (error) {
      // 用户点了停止:保留已收到的部分正文,不追加错误文案
      if (error?.name !== 'AbortError') {
        answer = `[错误] ${error.message}`;
      }
    } finally {
      if (answer) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: answer,
          intent: meta?.intent,
          tool_used: meta?.tool_used,
          tool_result: meta?.tool_result,
          sources: meta?.sources,
          errorHint,
          // S2 任务计划卡(intent=complex_task)
          taskProposal: meta?.task_proposal || null,
          proposalStatus: meta?.task_proposal ? 'idle' : undefined,
        }]);
      }
      if (confirmMessage) {
        setMessages(prev => [...prev, confirmMessage]);
      }
      setStreamingAnswer('');
      setStreamingMeta(null);
      setIsLoading(false);
      abortRef.current = null;
    }
  };

  /**
   * 发送一条问题(输入框、快捷问题、openAIDrawer、「直接回答」共用)。
   * 正在回答或问题为空时不发送,返回 false;否则返回 true。
   * @param {string} query
   * @param {{ skipTaskProposal?: boolean }} [options]
   * @returns {boolean}
   */
  const sendQuery = (query, options = {}) => {
    if (!query || !query.trim() || isLoading) return false;
    runQuery(query, options);
    return true;
  };

  useEffect(() => {
    sendQueryRef.current = sendQuery;
  });

  const handleSend = () => sendQuery(inputMessage);

  const handleStop = () => {
    if (abortRef.current) {
      abortRef.current();
      abortRef.current = null;
    }
  };

  const setProposalStatus = useCallback((index, proposalStatus) => {
    setMessages(prev => prev.map((m, i) => (i === index ? { ...m, proposalStatus } : m)));
  }, []);

  const handleCreateTask = async (index) => {
    const objective = messages[index]?.taskProposal?.objective;
    if (!objective) return;
    setProposalStatus(index, 'creating');
    try {
      await startAgentTask(objective, {
        conversationId: sessionId,
        onCreated: (card) => {
          setMessages(prev => [...prev, card]);
          setProposalStatus(index, 'created');
        },
      });
    } catch {
      setProposalStatus(index, 'error');
    }
  };

  const handleAnswerDirectly = (index) => {
    const objective = messages[index]?.taskProposal?.objective;
    if (!objective) return;
    setProposalStatus(index, 'answered');
    sendQuery(objective, { skipTaskProposal: true });
  };

  const handleClose = () => {
    setOpen(false);
  };

  const handleOpenFull = () => {
    setOpen(false);
    navigate('/smart-assistant');
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (isFullAssistantPage(pathname)) return null;

  const { pageContext, quickPrompts } = assistantContext;

  return (
    <>
      <FloatButton
        icon={<RobotOutlined />}
        tooltip="智能助手"
        style={{ right: 24, bottom: 24, zIndex: 1050 }}
        onClick={() => setOpen(true)}
      />
      <Drawer
        title={
          <div className="quick-assistant-drawer-header">
            <span className="quick-assistant-drawer-title">智能助手</span>
            <div className="quick-assistant-drawer-actions">
              <Button
                type="text"
                size="small"
                icon={<FullscreenOutlined />}
                onClick={handleOpenFull}
                title="打开完整页面"
              />
              <Button
                type="text"
                size="small"
                icon={<CloseOutlined />}
                onClick={handleClose}
              />
            </div>
          </div>
        }
        placement="right"
        width={420}
        onClose={handleClose}
        open={open}
        className="quick-assistant-drawer"
        styles={{ body: { padding: 0, display: 'flex', flexDirection: 'column' } }}
      >
        {(pageContext || quickPrompts.length > 0) && (
          <div className="qa-context-bar">
            {pageContext && (
              <Tag icon={<EyeOutlined />} color="blue" className="qa-page-context" data-testid="qa-page-context">
                正在查看:{pageContext.title} · {pageContext.label}
              </Tag>
            )}
            {quickPrompts.length > 0 && (
              <div className="qa-quick-prompts">
                {quickPrompts.map((prompt) => (
                  <Button
                    key={prompt.query}
                    size="small"
                    shape="round"
                    disabled={isLoading}
                    onClick={() => sendQuery(prompt.query)}
                    title={prompt.query}
                  >
                    {prompt.label}
                  </Button>
                ))}
              </div>
            )}
          </div>
        )}
        <div className="quick-assistant-messages">
          {messages.map((msg, index) => {
            if (msg.type === 'write_confirm') {
              return (
                <div key={msg.id || index} className="qa-message assistant">
                  <WriteConfirmCard confirmation={msg.confirmation} />
                </div>
              );
            }
            if (msg.type === 'collab_card') {
              return (
                <div key={msg.id || index} className="qa-collab-card">
                  <Suspense fallback={<Spin size="small" />}>
                    <ScenarioCollabCard
                      scenarioId={msg.scenarioId}
                      userInput={msg.userInput}
                      taskId={msg.taskId}
                      objective={msg.objective}
                    />
                  </Suspense>
                </div>
              );
            }
            return (
              <div key={index} className={`qa-message ${msg.role}`}>
                <div className="qa-message-content">
                  {msg.content}
                  {msg.tool_result && (
                    <ToolResult
                      intent={msg.intent}
                      result={msg.tool_result}
                      sources={msg.sources}
                    />
                  )}
                  {msg.role === 'assistant' && msg.taskProposal && (
                    <TaskProposalCard
                      proposal={msg.taskProposal}
                      status={msg.proposalStatus || 'idle'}
                      onCreate={() => handleCreateTask(index)}
                      onAnswerDirectly={() => handleAnswerDirectly(index)}
                    />
                  )}
                </div>
                {msg.role === 'assistant' && msg.errorHint && (
                  <Typography.Text
                    type="secondary"
                    data-testid="qa-error-hint"
                    style={{ display: 'block', marginTop: 4 }}
                  >
                    {msg.errorHint}
                  </Typography.Text>
                )}
              </div>
            );
          })}
          {streamingAnswer && (
            <div className="qa-message assistant">
              <div className="qa-message-content">
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
          {isLoading && !streamingAnswer && (
            <div className="qa-loading">
              <Spin size="small" />
              <span>思考中...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        <div className="quick-assistant-input">
          <TextArea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="问我任何问题..."
            disabled={isLoading}
            autoSize={{ minRows: 1, maxRows: 4 }}
            className="qa-input"
          />
          <FileAttachmentInput
            value={attachment}
            onChange={setAttachment}
            disabled={isLoading}
          />
          {isLoading ? (
            <Button
              danger
              icon={<StopOutlined />}
              onClick={handleStop}
              className="qa-stop-btn"
            />
          ) : (
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              disabled={!inputMessage.trim()}
              className="qa-send-btn"
            />
          )}
        </div>
      </Drawer>
    </>
  );
};

export default QuickAssistant;
