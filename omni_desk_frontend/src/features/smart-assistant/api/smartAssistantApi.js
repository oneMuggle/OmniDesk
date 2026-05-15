import apiClient from '../../../shared/api/apiClient';

const BASE_URL = '/smart-assistant';

/**
 * 发送智能聊天（SSE 流式）
 * 返回 ReadableStream
 */
export async function sendSmartChatStream(query, conversationId = null) {
  const body = { query };
  if (conversationId) {
    body.conversation_id = conversationId;
  }

  const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
  try {
    const response = await fetch(`${apiClient.defaults.baseURL}${BASE_URL}/chat/stream/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });

    if (response.status === 401) {
      throw new Error('AUTH_ERROR');
    }
    if (!response.ok) {
      throw new Error('NETWORK_ERROR');
    }

    return response.body;
  } catch (error) {
    if (error.message === 'AUTH_ERROR') {
      throw new Error('认证已过期，请重新登录');
    }
    if (error.message === 'NETWORK_ERROR') {
      throw new Error('网络连接失败，请检查网络');
    }
    // Fetch 错误通常是网络问题
    throw new Error('服务不可用，请稍后再试');
  }
}

/**
 * 获取会话列表
 */
export async function getSessions() {
  return apiClient.get(`${BASE_URL}/sessions/`);
}

/**
 * 创建新会话
 */
export async function createSession(title) {
  return apiClient.post(`${BASE_URL}/sessions/`, { title });
}

/**
 * 删除会话
 */
export async function deleteSession(sessionId) {
  return apiClient.delete(`${BASE_URL}/sessions/${sessionId}/`);
}

/**
 * 发送智能聊天请求
 */
export async function sendSmartChat(query, conversationId = null) {
  const body = { query };
  if (conversationId) {
    body.conversation_id = conversationId;
  }
  return apiClient.post(`${BASE_URL}/chat/`, body);
}

/**
 * 上传知识库文档
 */
export async function uploadKnowledgeDoc(file, title) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('title', title);
  return apiClient.post(`${BASE_URL}/knowledge-base/documents/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}

/**
 * 获取知识库文档列表
 */
export async function getKnowledgeDocs() {
  return apiClient.get(`${BASE_URL}/knowledge-base/documents/`);
}

/**
 * 删除知识库文档
 */
export async function deleteKnowledgeDoc(docId) {
  return apiClient.delete(`${BASE_URL}/knowledge-base/documents/${docId}/`);
}

/**
 * LLM 配置管理
 */
export async function getLlmConfigs() {
  return apiClient.get(`${BASE_URL}/llm-configs/`);
}

export async function addLlmConfig(data) {
  return apiClient.post(`${BASE_URL}/llm-configs/`, data);
}

export async function updateLlmConfig(id, data) {
  return apiClient.put(`${BASE_URL}/llm-configs/${id}/`, data);
}

export async function deleteLlmConfig(id) {
  return apiClient.delete(`${BASE_URL}/llm-configs/${id}/`);
}

/**
 * 根据 api_endpoint 和 api_key 获取上游可用模型列表
 */
export async function fetchLlmModels(apiEndpoint, apiKey) {
  return apiClient.post(`${BASE_URL}/llm-configs/fetch-models/`, {
    api_endpoint: apiEndpoint,
    api_key: apiKey,
  });
}
