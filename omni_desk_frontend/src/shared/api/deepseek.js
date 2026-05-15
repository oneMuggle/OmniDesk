import axios from 'axios';
import { getEnv } from '../utils/env';

let currentConfig = {
  apiKey: getEnv('VITE_DEEPSEEK_API_KEY', ''),
  apiEndpoint: getEnv('VITE_DEEPSEEK_ENDPOINT', 'https://api.deepseek.com/v1'),
  model: 'deepseek-chat',
};

export const setApiProvider = (config) => {
  currentConfig = { ...currentConfig, ...config };
};

export const getApiConfig = () => currentConfig;

export const createClient = (config) => {
  if (!config || !config.apiEndpoint || !config.apiKey) {
    return {
      chat: {
        completions: {
          create: async () => ({
            choices: [{ message: { content: 'Deepseek API未配置' } }],
          }),
        },
      },
    };
  }

  const client = axios.create({
    baseURL: currentConfig.apiEndpoint,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${currentConfig.apiKey}`,
    },
  });

  return {
    chat: {
      completions: {
        create: async (params) => {
          const response = await client.post('/chat/completions', {
            model: currentConfig.model,
            messages: params.messages,
            temperature: params.temperature || 0.7,
            stream: params.stream || false,
          });

          if (response.status !== 200) {
            throw new Error(`API请求失败: ${response.status} ${response.statusText}`);
          }

          return response.data;
        },
      },
    },
  };
};
