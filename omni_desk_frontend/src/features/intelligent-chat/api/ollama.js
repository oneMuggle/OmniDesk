import axios from 'axios';
import apiClient from '../../../api/apiClient';
import { OLLAMA_API_URL } from '../../../config/config';

// 创建独立的Ollama客户端
const ollamaClient = axios.create({
  baseURL: OLLAMA_API_URL,
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

export const getOllamaConfigs = () => apiClient.get('/api/config/ollama-configs/');
export const addOllamaConfig = (config) => apiClient.post('/api/config/ollama-configs/', config);
export const updateOllamaConfig = (id, config) => apiClient.put(`/api/config/ollama-configs/${id}/`, config);
export const deleteOllamaConfig = (id) => apiClient.delete(`/api/config/ollama-configs/${id}/`);

export const chatCompletion = async (config, messages, onUpdate) => {
  const ollamaClient = axios.create({
    baseURL: config.api_endpoint,
    headers: { 'Content-Type': 'application/json' }
  });

  try {
    const prompt = messages.map(m => `${m.role}: ${m.content}`).join('\n\n');

    // 修改为流式请求
    await ollamaClient.post('/api/generate', {
      model: config.model,
      prompt: prompt,
      stream: true, // 开启流式传输
      context: config.context || null,
      options: {
        temperature: config.temperature,
        top_p: config.top_p,
      }
    }, {
      // 启用响应流处理
      onDownloadProgress: (progressEvent) => {
        const data = progressEvent.event.currentTarget.response;
        const lines = data.split('\n');
        let latestContent = '';
        let latestContext = null;

        for (const line of lines) {
          if (line.trim() === '') continue;
          try {
            const json = JSON.parse(line);
            if (json.response) {
              latestContent += json.response;
            }
            if (json.context) {
              latestContext = json.context;
            }
            // 调用回调函数更新UI
            if (onUpdate) {
              onUpdate({
                content: latestContent,
                context: latestContext,
                done: json.done || false // 判断是否完成
              });
            }
          } catch (e) {
            console.error("Error parsing stream data:", e, "Line:", line);
          }
        }
      }
    });

    // 对于流式请求，实际的响应内容会在onDownloadProgress中处理
    // 这里可以返回一个指示完成的对象
    return {
      role: 'assistant',
      content: '', // 内容已通过onUpdate回调处理
      context: null, // context已通过onUpdate回调处理
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
    const response = await ollamaClient.get('/api/tags');
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
    const response = await apiClient.get('/api/config/');
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
    const response = await apiClient.post('/api/config/', config);
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