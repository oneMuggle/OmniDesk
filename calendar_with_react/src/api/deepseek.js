let currentConfig = {
  apiKey: '',
  apiEndpoint: 'https://api.deepseek.com/v1',
  model: 'deepseek-chat'
};

export const setApiProvider = (config) => {
  currentConfig = { ...currentConfig, ...config };
};

export const getApiConfig = () => currentConfig;

export const createClient = () => {
  return {
    chat: {
      completions: {
        create: async (params) => {
          const response = await fetch(currentConfig.apiEndpoint + '/chat/completions', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${currentConfig.apiKey}`
            },
            body: JSON.stringify({
              model: currentConfig.model,
              messages: params.messages,
              temperature: params.temperature || 0.7,
              stream: params.stream || false
            })
          });
          
          if (!response.ok) {
            throw new Error(`API请求失败: ${response.status} ${response.statusText}`);
          }
          
          return params.stream ? response.body : response.json();
        }
      }
    }
  };
};
