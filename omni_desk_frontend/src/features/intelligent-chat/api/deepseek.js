import axios from 'axios';
import { API_BASE_URL } from '../../../config/config';

const API_URL = API_BASE_URL;

let currentConfig = {
  apiKey: process.env.REACT_APP_DEEPSEEK_API_KEY,
  apiEndpoint: process.env.REACT_APP_DEEPSEEK_API_ENDPOINT,
  model: 'deepseek-chat'
};

// 新增上下文管理函数
let conversationHistory = [];

export const setApiProvider = (config) => {
  currentConfig = { ...currentConfig, ...config };
};

export const getApiConfig = () => currentConfig;

export const clearConversationHistory = () => {
  conversationHistory = [];
};

export const generateDocument = async (templateId, variables) => {
  try {
    const response = await axios.post(`${API_URL}/documents/generated/`, {
      template: templateId,
      variables_used: variables,
      content: "" // 内容由后端生成
    });

    // 返回包含生成文档完整信息的对象
    return {
      ...response.data,
      content: response.data.content.replace(/{{\s*([^}]+)\s*}}/g, (match, p1) => variables[p1.trim()] || match)
    };
    
  } catch (error) {
    console.error('文档生成失败:', error);
    throw new Error(`文档生成失败: ${error.response?.data?.detail || error.message}`);
  }
};

export const uploadTemplate = async (formData) => {
  try {
    const response = await axios.post(`${API_URL}/documents/templates/upload/`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    return response.data;
  } catch (error) {
    console.error('模板上传失败:', error);
    throw new Error(`模板上传失败: ${error.response?.data?.detail || error.message}`);
  }
};

export const getDocumentTemplates = async (projectId = null) => {
  try {
    let url = `${API_URL}/documents/templates/`;
    if (projectId) {
      url += `?project_id=${projectId}`;
    }
    const response = await axios.get(url);
    return response.data;
  } catch (error) {
    console.error('获取模板失败:', error);
    throw new Error(`获取模板失败: ${error.response?.data?.detail || error.message}`);
  }
};

export const createClient = (withContext = false) => {
  // 验证配置完整性（改为可选配置）
  if (!currentConfig.apiEndpoint || !currentConfig.apiKey) {
    console.warn('Deepseek API配置不完整，相关功能将被禁用');
    return { 
      chat: { 
        completions: { 
          create: async () => ({ choices: [{ message: { content: "Deepseek API未配置" } }] })
        } 
      } 
    };
  }

  const client = axios.create({
    baseURL: currentConfig.apiEndpoint,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${currentConfig.apiKey}`
    }
  });

  return {
    chat: {
      completions: {
        create: async (params) => {
          const response = await client.post('/chat/completions', {
            model: currentConfig.model,
            messages: params.messages,
            temperature: params.temperature || 0.7,
            stream: params.stream || false
          });
          
          if (response.status !== 200) {
            throw new Error(`API请求失败: ${response.status} ${response.statusText}`);
          }
          
          const result = params.stream ? response.body : response.data;
          
          if (withContext) {
            conversationHistory.push(...params.messages);
            conversationHistory.push(result.choices[0].message);
            // 保持最近10轮对话上下文
            if (conversationHistory.length > 20) {
              conversationHistory = conversationHistory.slice(-20);
            }
          }
          return result;
        }
      }
    }
  };
};