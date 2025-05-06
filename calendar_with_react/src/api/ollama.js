import apiClient from './apiClient';

const ollamaClient = apiClient;

// 初始化时从后端获取配置
(async function initOllamaConfig() {
  try {
    const response = await apiClient.get('/config/');
    if (response.data.OLLAMA_ENDPOINT) {
      ollamaClient.defaults.baseURL = response.data.OLLAMA_ENDPOINT;
    }
  } catch (error) {
    console.log('使用默认OLLAMA配置');
  }
})();

export const chatCompletion = async (config, messages) => {
  try {
    // 将消息历史转换为Ollama格式
    const prompt = messages.map(m => `${m.role}: ${m.content}`).join('\n\n');
    
    const response = await ollamaClient.post('/generate', {
      model: config.model,
      prompt: prompt,
      stream: false,
      context: config.context || null
    });
    
    return {
      role: 'assistant',
      content: response.data.response,
      context: response.data.context,
      usage: {
        prompt_tokens: 0,
        completion_tokens: 0
      }
    };
  } catch (error) {
    console.error('Ollama API error:', error);
    throw new Error(`Ollama API请求失败: ${error.message}`);
  }
};

export const getModels = async () => {
  try {
    const response = await ollamaClient.get('/tags');
    return response.data.models.map(model => model.name);
  } catch (error) {
    console.error('获取模型列表失败:', error);
    throw new Error(`无法获取模型列表: ${error.message}`);
  }
};

export const setApiProvider = (config) => {
  apiClient.defaults.baseURL = config.apiEndpoint;
};

export const getConfig = async () => {
  try {
    const response = await apiClient.get('/config/');
    return response.data;
  } catch (error) {
    if (error.response?.status === 401) {
      window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
      return;
    }
    throw error.response?.data || { message: '获取OLLAMA配置失败' };
  }
};

export const setConfig = async (config) => {
  try {
    const response = await apiClient.post('/config/', config);
    return response.data;
  } catch (error) {
    if (error.response?.status === 401) {
      window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
      return;
    }
    throw error.response?.data || { message: '保存OLLAMA配置失败' };
  }
};
