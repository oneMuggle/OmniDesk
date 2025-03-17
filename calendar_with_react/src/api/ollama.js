import axios from 'axios';

const ollamaClient = axios.create({
  baseURL: process.env.REACT_APP_OLLAMA_ENDPOINT || 'http://localhost:11434/api',
  headers: {
    'Content-Type': 'application/json'
  }
});

export const chatCompletion = async (config, messages) => {
  try {
    const response = await ollamaClient.post('/generate', {
      model: config.model,
      prompt: messages[messages.length - 1].content,
      stream: false
    });
    
    return {
      content: response.data.response,
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
    const response = await ollamaClient.get('/v1/models');
    return response.data.data.map(model => model.id.replace(/^models\//, ''));
  } catch (error) {
    console.error('获取模型列表失败:', error);
    throw new Error(`无法获取模型列表: ${error.message}`);
  }
};

export const setApiProvider = (config) => {
  ollamaClient.defaults.baseURL = config.apiEndpoint;
};
