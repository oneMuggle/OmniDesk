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
      try {
        const response = await getOllamaConfigs();
        const configsData = response.data && Array.isArray(response.data.data) ? response.data.data : [];
        setConfigs(configsData);
        const defaultConfig = configsData.find(c => c.is_default);
        setSelectedConfig(defaultConfig || (configsData.length > 0 ? configsData[0] : null));
      } catch (error) {
        console.error('Failed to load configs:', error);
        setConfigs([]);
      }
    };
    loadConfigs();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || !selectedConfig) return;

    const newMessage = { role: 'user', content: inputMessage };
    const newMessages = [...messages, newMessage];
    setMessages(newMessages); // 立即显示用户消息
    setInputMessage(''); // 清空输入框
    setIsLoading(true);

    try {
      let currentAssistantMessage = { role: 'assistant', content: '', context: null };
      let updatedConversationHistory = [...conversationHistory, newMessage]; // 用于传递给chatCompletion
      
      const context = conversationHistory.length > 0
        ? conversationHistory[conversationHistory.length - 1].context
        : null;

      // 在messages中为AI的回答预留位置
      const aiMessageIndex = newMessages.length;
      setMessages(prev => [...prev, currentAssistantMessage]);

      await chatCompletion(
        { ...selectedConfig, context }, // 直接使用selectedConfig
        updatedConversationHistory,
        ({ content, context, done }) => {
          // 逐步更新AI消息内容
          currentAssistantMessage.content = content;
          currentAssistantMessage.context = context;
          setMessages(prev => {
            const updated = [...prev];
            updated[aiMessageIndex] = { ...currentAssistantMessage };
            return updated;
          });

          // 如果流式传输完成，则更新conversationHistory
          if (done) {
            setConversationHistory([...updatedConversationHistory, currentAssistantMessage]);
            setIsLoading(false); // 流式传输完成后才停止加载
          }
        }
      );
    } catch (error) {
      console.error('API Error:', error);
      setIsLoading(false); // 发生错误时停止加载
      setMessages(prev => {
        const current = Array.isArray(prev) ? prev : [];
        // 添加错误提示消息，可能需要调整索引或消息类型
        return [...current, {
          role: 'system',
          content: '抱歉，请求失败，请稍后再试'
        }];
      });
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
