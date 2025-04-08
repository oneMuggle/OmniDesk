import axios from 'axios';

const ollamaClient = axios.create({
  baseURL: process.env.REACT_APP_OLLAMA_ENDPOINT || 'http://localhost:11434/api',
  headers: {
    'Content-Type': 'application/json'
  }
});

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
