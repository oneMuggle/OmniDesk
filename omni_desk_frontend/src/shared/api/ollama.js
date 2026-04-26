import axios from 'axios';
import apiClient from './apiClient';

export const getOllamaConfigs = () => apiClient.get('config/ollama-configs/');
export const addOllamaConfig = (config) => apiClient.post('config/ollama-configs/', config);
export const updateOllamaConfig = (id, config) => apiClient.put(`config/ollama-configs/${id}/`, config);
export const deleteOllamaConfig = (id) => apiClient.delete(`config/ollama-configs/${id}/`);

export const chatCompletion = async (config, messages, onUpdate) => {
  const client = axios.create({
    baseURL: config.api_endpoint,
    headers: { 'Content-Type': 'application/json' },
  });

  try {
    const prompt = messages.map(m => `${m.role}: ${m.content}`).join('\n\n');

    await client.post('generate', {
      model: config.model,
      prompt,
      stream: true,
      context: config.context || null,
      options: {
        temperature: config.temperature,
        top_p: config.top_p,
      },
    }, {
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
            if (onUpdate) {
              onUpdate({
                content: latestContent,
                context: latestContext,
                done: json.done || false,
              });
            }
          } catch (e) {
            console.error('Error parsing stream data:', e, 'Line:', line);
          }
        }
      },
    });

    return {
      role: 'assistant',
      content: '',
      context: null,
      usage: { prompt_tokens: 0, completion_tokens: 0 },
    };
  } catch (error) {
    throw new Error(`Ollama API请求失败: ${error.message}`);
  }
};

export const getModels = async () => {
  const response = await apiClient.get('config/');
  const endpoint = response.data.OLLAMA_ENDPOINT;
  if (!endpoint) {
    throw new Error('Ollama endpoint未配置');
  }
  const client = axios.create({ baseURL: endpoint });
  const res = await client.get('tags');
  return res.data.models.map(model => model.name);
};

export const setApiProvider = (config) => {
  // Used by ApiProvider to sync config
};

export const getOllamaModelsFromEndpoint = async (apiEndpoint) => {
  const fullApiEndpoint = apiEndpoint.startsWith('http://') || apiEndpoint.startsWith('https://')
    ? apiEndpoint
    : `http://${apiEndpoint}`;
  const response = await axios.get(`${fullApiEndpoint}/v1/models`);
  return response.data;
};
