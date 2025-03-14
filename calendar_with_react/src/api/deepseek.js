import OpenAI from 'openai';

export const deepseekClient = new OpenAI({
  baseURL: 'https://api.deepseek.com/v1', // 根据文档应使用基础路径
  apiKey: process.env.REACT_APP_DEEPSEEK_API_KEY,
  dangerouslyAllowBrowser: true
});
