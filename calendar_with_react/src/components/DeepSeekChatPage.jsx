import React, { useState, useEffect, useContext } from 'react';
import { createClient } from '../api/deepseek';
import { ApiContext } from '../context/ApiProvider';
import './DeepSeekChatPage.css';

const DeepSeekChatPage = () => {
  const { conversationHistory, setConversationHistory } = useContext(ApiContext);
  const [inputMessage, setInputMessage] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setMessages(conversationHistory);
  }, [conversationHistory]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim()) return;

    try {
      setIsLoading(true);
      const client = createClient(true);
      const newMessage = { role: 'user', content: inputMessage };
      
      const response = await client.chat.completions.create({
        messages: [...conversationHistory, newMessage],
        temperature: 0.7
      });

      const aiMessage = response.choices[0].message;
      setConversationHistory([...conversationHistory, newMessage, aiMessage]);
      setInputMessage('');
    } catch (error) {
      console.error('API Error:', error);
      setMessages(prev => [...prev, { 
        role: 'system', 
        content: '抱歉，请求失败，请稍后再试' 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="deepseek-chat-container">
      <div className="chat-messages">
        {(messages || []).map((msg, index) => (
          <div key={index} className={`message ${msg.role}`}>
            <div className="message-content">
              {msg.content}
            </div>
          </div>
        ))}
        {isLoading && <div className="loading-indicator">思考中...</div>}
      </div>
      <form onSubmit={handleSubmit} className="chat-input-form">
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          placeholder="输入你的问题..."
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading}>
          {isLoading ? '发送中...' : '发送'}
        </button>
      </form>
    </div>
  );
};

export default DeepSeekChatPage;
