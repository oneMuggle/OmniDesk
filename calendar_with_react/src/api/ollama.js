import axios from 'axios';

// 创建并导出api实例
export const api = axios.create({
  baseURL: `${process.env.REACT_APP_API_BASE_URL}/api` || 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json'
  }
});

const ollamaClient = axios.create({
  baseURL: 'http://localhost:11434/api', // 默认值，会被配置覆盖
  headers: {
    'Content-Type': 'application/json'
  }
});

// 初始化时从后端获取配置
(async function initOllamaConfig() {
  try {
    const response = await api.get('/config/');
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
  ollamaClient.defaults.baseURL = config.apiEndpoint;
};
