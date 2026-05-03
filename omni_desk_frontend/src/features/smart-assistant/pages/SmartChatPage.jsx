import { useState, useRef, useEffect } from 'react';
import { sendSmartChat } from '../api/smartAssistantApi';
import ToolResult from '../components/ToolResult';
import './SmartChatPage.css';

const SmartChatPage = () => {
  const [inputMessage, setInputMessage] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim()) return;

    const userMessage = { role: 'user', content: inputMessage };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await sendSmartChat(inputMessage);
      const result = response.data;
      const assistantMessage = {
        role: 'assistant',
        content: result.answer,
        intent: result.intent,
        tool_used: result.tool_used,
        tool_result: result.tool_result,
        sources: result.sources,
      };
      setMessages([...newMessages, assistantMessage]);
    } catch (error) {
      setMessages([...newMessages, {
        role: 'system',
        content: '抱歉，请求失败，请稍后再试',
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="smart-chat-container">
      <div className="smart-chat-header">
        <h2>智能助手</h2>
      </div>
      <div className="smart-chat-messages">
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.role}`}>
            <div className="message-content">
              {msg.content}
              {msg.tool_result && <ToolResult intent={msg.intent} result={msg.tool_result} sources={msg.sources} />}
            </div>
          </div>
        ))}
        {isLoading && <div className="loading-indicator">思考中...</div>}
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
