import axios from 'axios';

let currentConfig = {
  apiKey: process.env.REACT_APP_DEEPSEEK_API_KEY,
  apiEndpoint: process.env.REACT_APP_DEEPSEEK_API_ENDPOINT,
  model: 'deepseek-chat'
};

export const setApiProvider = (config) => {
  currentConfig = { ...currentConfig, ...config };
};

export const getApiConfig = () => currentConfig;

export const createClient = () => {
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
          
          return params.stream ? response.body : response.json();
        }
      }
    }
  };
};
