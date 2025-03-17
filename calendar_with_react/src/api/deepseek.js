import axios from 'axios';

let currentConfig = {
  apiKey: process.env.REACT_APP_DEEPSEEK_API_KEY,
  apiEndpoint: process.env.REACT_APP_DEEPSEEK_API_ENDPOINT,
  model: 'deepseek-chat'
};

// 新增上下文管理函数
let conversationHistory = [];

export const setApiProvider = (config) => {
  currentConfig = { ...currentConfig, ...config };
};

export const getApiConfig = () => currentConfig;

export const clearConversationHistory = () => {
  conversationHistory = [];
};

export const createClient = (withContext = false) => {
  // 验证配置完整性
  if (!currentConfig.apiEndpoint || !currentConfig.apiKey) {
    throw new Error('Deepseek API配置不完整，请检查API终结点和密钥');
  }

  const client = axios.create({
    baseURL: currentConfig.apiEndpoint,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${currentConfig.apiKey}`
    }
  });

  return {
    chat: {
      completions: {
        create: async (params) => {
          const response = await client.post('/chat/completions', {
            model: currentConfig.model,
            messages: params.messages,
            temperature: params.temperature || 0.7,
            stream: params.stream || false
          });
          
          if (response.status !== 200) {
            throw new Error(`API请求失败: ${response.status} ${response.statusText}`);
          }
          
          const result = params.stream ? response.body : response.data;
          
          if (withContext) {
            conversationHistory.push(...params.messages);
            conversationHistory.push(result.choices[0].message);
            // 保持最近10轮对话上下文
            if (conversationHistory.length > 20) {
              conversationHistory = conversationHistory.slice(-20);
            }
          }
          return result;
        }
      }
    }
  };
};
