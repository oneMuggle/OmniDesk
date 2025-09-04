import axios from 'axios';
import apiClient from './apiClient';

// 创建独立的Ollama客户端
const ollamaClient = axios.create({
  baseURL: process.env.REACT_APP_OLLAMA_ENDPOINT || 'http://localhost:11434/api',
  headers: {
    'Content-Type': 'application/json'
  }
});

// 初始化配置
(async function initOllamaConfig() {
  try {
    const response = await axios.get('/api/config/');
    if (response.data.OLLAMA_ENDPOINT) {
      ollamaClient.defaults.baseURL = response.data.OLLAMA_ENDPOINT;
    }
  } catch (error) {
    console.log('使用环境变量中的OLLAMA配置');
  }
})();

export const getOllamaConfigs = () => apiClient.get('/config/ollama-configs/');
export const addOllamaConfig = (config) => apiClient.post('/config/ollama-configs/', config);
export const updateOllamaConfig = (id, config) => apiClient.put(`/config/ollama-configs/${id}/`, config);
export const deleteOllamaConfig = (id) => apiClient.delete(`/config/ollama-configs/${id}/`);

export const chatCompletion = async (config, messages) => {
  const ollamaClient = axios.create({
    baseURL: config.api_endpoint,
    headers: { 'Content-Type': 'application/json' }
  });

  try {
    // 将消息历史转换为Ollama格式
    const prompt = messages.map(m => `${m.role}: ${m.content}`).join('\n\n');
    
    const response = await ollamaClient.post('/generate', {
      model: config.model,
      prompt: prompt,
      stream: false,
      context: config.context || null,
      options: {
        temperature: config.temperature,
        top_p: config.top_p,
      }
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
  ollamaClient.defaults.baseURL = config.apiEndpoint;
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

export const getOllamaModelsFromEndpoint = async (apiEndpoint) => {
  try {
    // 确保apiEndpoint包含协议，如果缺少则默认为http://
    const fullApiEndpoint = apiEndpoint.startsWith('http://') || apiEndpoint.startsWith('https://')
      ? apiEndpoint
      : `http://${apiEndpoint}`;
    const response = await axios.get(`${fullApiEndpoint}/v1/models`);
    return response.data;
  } catch (error) {
    console.error('Failed to fetch models from endpoint:', error);
    throw error;
  }
};
