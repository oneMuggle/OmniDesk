import { useState, useRef, useEffect } from 'react';
import { FloatButton, Drawer, Input, Button, Spin, Typography } from 'antd';
import { RobotOutlined, SendOutlined, FullscreenOutlined, CloseOutlined, StopOutlined } from '@ant-design/icons';
import { sendSmartChatStream, createSession, resolveErrorHint } from '../../features/smart-assistant/api/smartAssistantApi';
import { consumeSSEStream } from '../../features/smart-assistant/utils/chatUtils';
import ToolResult from '../../features/smart-assistant/components/ToolResult';
import FileAttachmentInput from './FileAttachmentInput';
import { useNavigate } from 'react-router-dom';
import './QuickAssistant.css';

const { TextArea } = Input;

const QuickAssistant = () => {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [attachment, setAttachment] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [streamingAnswer, setStreamingAnswer] = useState('');
  const [streamingMeta, setStreamingMeta] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [isCancelled, setIsCancelled] = useState(false);
  // 失败辅助提示(输出契约 format_version:1,done/session 事件的 kind/hint);
  // 旧事件无字段时保持 null,不渲染提示行
  const [errorHint, setErrorHint] = useState(null);
  const messagesEndRef = useRef(null);
  const abortRef = useRef(null);
  const navigate = useNavigate();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingAnswer]);

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

  const handleSend = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const currentSessionId = await ensureSession();
    if (!currentSessionId) return;

    const userMessage = { role: 'user', content: inputMessage, attachment: attachment ? attachment.name : null };
    setMessages(prev => [...prev, userMessage]);
    const query = inputMessage;
    setInputMessage('');
    setAttachment(null);
    setIsLoading(true);
    setStreamingAnswer('');
    setStreamingMeta(null);
    setErrorHint(null);
    setIsCancelled(false);

    try {
      const { bodyPromise, abort } = sendSmartChatStream(query, currentSessionId, attachment);
      abortRef.current = abort;
      const stream = await bodyPromise;

      if (!stream) {
        // 用户取消或连接失败
        return;
      }

      // 本次流是否已产出正文(用于失败无内容时的兜底气泡)
      let receivedContent = false;

      // R4-B2:SSE 读取骨架收敛到共享 consumeSSEStream(chatUtils.js),
      // 事件处理在此回调内完成,行为与旧版内联循环一致
      await consumeSSEStream(stream, (event) => {
        if (event.type === 'meta') {
          setStreamingMeta(event);
        } else if (event.type === 'chunk') {
          receivedContent = true;
          setStreamingAnswer(prev => prev + event.content);
        } else if (event.type === 'done' || event.type === 'session') {
          // 输出契约(format_version:1):失败时 done/session 事件携带 kind/hint;
          // 旧事件无这些字段 → resolveErrorHint 返回 undefined,行为与旧版一致
          const hint = resolveErrorHint(event);
          if (hint) {
            setErrorHint(hint);
            // 失败但流未产出任何正文时,兜底一条失败气泡,保证提示行有载体
            if (event.type === 'done' && !receivedContent) {
              setStreamingAnswer('回答生成失败');
            }
          }
        }
      });
    } catch (error) {
      if (!isCancelled) {
        setStreamingAnswer(`[错误] ${error.message}`);
      }
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  };

  const handleStop = () => {
    if (abortRef.current) {
      setIsCancelled(true);
      abortRef.current();
      abortRef.current = null;
    }
  };

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
        // 失败辅助提示(输出契约);旧事件无 kind/hint 时为 null,不渲染提示行
        errorHint,
      };
      setMessages(prev => [...prev, assistantMessage]);
      setStreamingAnswer('');
      setStreamingMeta(null);
      setErrorHint(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, streamingAnswer, streamingMeta]);

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
        <div className="quick-assistant-messages">
          {messages.map((msg, index) => (
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
          ))}
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
