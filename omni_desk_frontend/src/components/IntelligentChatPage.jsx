import React, { useState, useEffect, useContext } from 'react';
import { chatCompletion, getOllamaConfigs } from '../api/ollama';
import { ApiContext } from '../context/ApiProvider';
import ThinkContent from './ThinkContent';
import './IntelligentChatPage.css';

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

const IntelligentChatPage = () => {
  const { conversationHistory, setConversationHistory } = useContext(ApiContext);
  const [inputMessage, setInputMessage] = useState('');
  const [messages, setMessages] = useState(() => {
    return Array.isArray(conversationHistory) ? conversationHistory : [];
  });
  const [isLoading, setIsLoading] = useState(false);
  const [configs, setConfigs] = useState([]);
  const [selectedConfig, setSelectedConfig] = useState(null);

  useEffect(() => {
    setMessages(conversationHistory);
  }, [conversationHistory]);

  useEffect(() => {
    const loadConfigs = async () => {
      const response = await getOllamaConfigs();
      setConfigs(response.data);
      const defaultConfig = response.data.find(c => c.is_default);
      setSelectedConfig(defaultConfig || (response.data.length > 0 ? response.data[0] : null));
    };
    loadConfigs();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || !selectedConfig) return;

    try {
      setIsLoading(true);
      const newMessage = { role: 'user', content: inputMessage };
      const context = conversationHistory.length > 0
        ? conversationHistory[conversationHistory.length - 1].context
        : null;
      
      const configToSend = { ...selectedConfig, context };
      // 确保api_endpoint以/api结尾
      if (configToSend.api_endpoint && !configToSend.api_endpoint.endsWith('/api')) {
        configToSend.api_endpoint = `${configToSend.api_endpoint}/api`;
      }
      
      const response = await chatCompletion(
        configToSend,
        [...conversationHistory, newMessage]
      );

      const aiMessage = {
        role: response.role,
        content: response.content,
        context: response.context
      };
      setConversationHistory([...conversationHistory, newMessage, aiMessage]);
      setInputMessage('');
    } catch (error) {
      console.error('API Error:', error);
      setMessages(prev => {
        const current = Array.isArray(prev) ? prev : [];
        return [...current, {
          role: 'system',
          content: '抱歉，请求失败，请稍后再试'
        }];
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="intelligent-chat-container">
      <div className="config-selector">
        <select
          value={selectedConfig ? selectedConfig.id : ''}
          onChange={(e) => {
            const config = configs.find(c => c.id === parseInt(e.target.value));
            setSelectedConfig(config);
          }}
        >
          {configs.map(config => (
            <option key={config.id} value={config.id}>{config.alias}</option>
          ))}
        </select>
      </div>
      <div className="chat-messages">
        {(messages || []).map((msg, index) => (
          <div key={index} className={`message ${msg.role}`}>
            <div className="message-content">
              {parseThinkContent(msg.content).mainContent}
              <ThinkContent content={parseThinkContent(msg.content).thinkContent} />
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

export default IntelligentChatPage;
