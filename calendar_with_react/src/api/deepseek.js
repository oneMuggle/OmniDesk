import OpenAI from 'openai';

export const deepseekClient = new OpenAI({
  baseURL: 'https://api.deepseek.com',
  apiKey: process.env.REACT_APP_DEEPSEEK_API_KEY,
  dangerouslyAllowBrowser: true
});
