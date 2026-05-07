import { useState, useRef, useEffect } from 'react';
import { FloatButton, Drawer, Input, Button, Spin } from 'antd';
import { RobotOutlined, SendOutlined, FullscreenOutlined, CloseOutlined } from '@ant-design/icons';
import { sendSmartChatStream, createSession } from '../../features/smart-assistant/api/smartAssistantApi';
import ToolResult from '../../features/smart-assistant/components/ToolResult';
import { useNavigate } from 'react-router-dom';
import './QuickAssistant.css';

const { TextArea } = Input;

const QuickAssistant = () => {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [streamingAnswer, setStreamingAnswer] = useState('');
  const [streamingMeta, setStreamingMeta] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const messagesEndRef = useRef(null);
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

  const handleSend = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const currentSessionId = await ensureSession();
    if (!currentSessionId) return;

    const userMessage = { role: 'user', content: inputMessage };
    setMessages(prev => [...prev, userMessage]);
    const query = inputMessage;
    setInputMessage('');
    setIsLoading(true);
    setStreamingAnswer('');
    setStreamingMeta(null);

    try {
      const stream = await sendSmartChatStream(query, currentSessionId);
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
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            disabled={isLoading || !inputMessage.trim()}
            className="qa-send-btn"
          />
        </div>
      </Drawer>
    </>
  );
};

export default QuickAssistant;
