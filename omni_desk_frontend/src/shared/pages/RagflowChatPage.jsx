import { useState, useEffect, useContext } from 'react';
import { ApiContext } from '../context/ApiProvider';
import ThinkContent from '../components/ThinkContent';
import './RagflowChatPage.css'; // 稍后创建此CSS文件
import apiClient from '../api/apiClient'; // 假设你有一个通用的API客户端
import { logger } from '../utils/logger';

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

const RagflowChatPage = () => {
  const { conversationHistory, setConversationHistory } = useContext(ApiContext);
  const [inputMessage, setInputMessage] = useState('');
  const [messages, setMessages] = useState(() => {
    return Array.isArray(conversationHistory) ? conversationHistory : [];
  });
  const [isLoading, setIsLoading] = useState(false);
  const [ragflowConfig, setRagflowConfig] = useState(null); // 存储当前选中的Ragflow配置
  const [ragflowConfigs, setRagflowConfigs] = useState([]); // 存储所有可用的Ragflow配置
  const [selectedConfigId, setSelectedConfigId] = useState(''); // 存储选中的配置ID

  useEffect(() => {
    setMessages(conversationHistory);
  }, [conversationHistory]);

  useEffect(() => {
    // 获取所有Ragflow配置
    const fetchRagflowConfigs = async () => {
      try {
        const response = await apiClient.get('ragflow-service/configs/');
        setRagflowConfigs(response.data.results || []);
        if (response.data.results && response.data.results.length > 0) {
          // 默认选中第一个激活的配置
          const activeConfig = response.data.results.find(config => config.is_active);
          if (activeConfig) {
            setSelectedConfigId(activeConfig.id);
            setRagflowConfig(activeConfig);
          } else {
            setSelectedConfigId(response.data.results[0].id);
            setRagflowConfig(response.data.results[0]);
          }
        }
      } catch (error) {
        logger.error('Error fetching Ragflow configs:', error);
      }
    };
    fetchRagflowConfigs();
  }, []);

  const handleConfigChange = (e) => {
    const configId = e.target.value;
    setSelectedConfigId(configId);
    const selected = ragflowConfigs.find(config => config.id === parseInt(configId));
    setRagflowConfig(selected);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || !ragflowConfig) return;

    try {
      setIsLoading(true);
      const newMessage = { role: 'user', content: inputMessage };
      // 从conversationHistory中提取conversation_id，如果存在的话
      const lastMessage = conversationHistory[conversationHistory.length - 1];
      const conversationId = lastMessage && lastMessage.conversation_id ? lastMessage.conversation_id : null;

      const response = await apiClient.post(
        `ragflow-service/configs/${ragflowConfig.id}/query/`,
        { 
          question: inputMessage,
          conversation_id: conversationId // 传递conversation_id
        }
      );

      const aiMessage = {
        role: 'assistant', // 假设Ragflow返回的都是助手消息
        content: response.data.answer, // 根据Ragflow实际返回的字段调整
        conversation_id: response.data.conversation_id // 假设Ragflow返回conversation_id
      };
      setConversationHistory([...conversationHistory, newMessage, aiMessage]);
      setInputMessage('');
    } catch (error) {
      logger.error('Ragflow API Error:', error);
      setMessages(prev => {
        const current = Array.isArray(prev) ? prev : [];
        return [...current, { 
          role: 'system', 
          content: `抱歉，Ragflow请求失败: ${error.response?.data?.detail || error.message}` 
        }];
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="ragflow-chat-container">
      <h1>Ragflow 智能问答</h1>
      {ragflowConfigs.length > 0 && (
        <div className="ragflow-config-selector">
          <label htmlFor="ragflow-config">选择 Ragflow 配置:</label>
          <select id="ragflow-config" value={selectedConfigId} onChange={handleConfigChange} disabled={isLoading}>
            {ragflowConfigs.map(config => (
              <option key={config.id} value={config.id}>{config.name}</option>
            ))}
          </select>
        </div>
      )}
      {ragflowConfigs.length === 0 && !isLoading && (
        <div className="error-message">
          <p>没有可用的 Ragflow 配置。请在后端管理界面添加并激活 Ragflow 配置。</p>
        </div>
      )}
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
          disabled={isLoading || !selectedConfigId}
        />
        <button type="submit" disabled={isLoading || !selectedConfigId}>
          {isLoading ? '发送中...' : '发送'}
        </button>
      </form>
    </div>
  );
};

export default RagflowChatPage;