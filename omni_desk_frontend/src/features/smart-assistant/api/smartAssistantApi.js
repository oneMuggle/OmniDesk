import apiClient from '../../../shared/api/apiClient';

const BASE_URL = 'smart-assistant';

/**
 * 发送智能聊天（SSE 流式）
 * 返回 { bodyPromise, abort } 对象
 * - bodyPromise: Promise<ReadableStream>，解析为响应体
 * - abort: 取消请求的函数
 */
export function sendSmartChatStream(query, conversationId = null) {
  const abortController = new AbortController();

  const requestPromise = (async () => {
    const body = { query };
    if (conversationId) {
      body.conversation_id = conversationId;
    }

    const authTokens = JSON.parse(localStorage.getItem('authTokens') || sessionStorage.getItem('authTokens') || '{}');
    const token = authTokens.access;

    try {
      const response = await fetch(`${apiClient.defaults.baseURL}${BASE_URL}/chat/stream/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
        signal: abortController.signal,
      });

      if (response.status === 401) {
        throw new Error('AUTH_ERROR');
      }
      if (!response.ok) {
        throw new Error('NETWORK_ERROR');
      }

      return response.body;
    } catch (error) {
      if (error.name === 'AbortError') {
        // 用户主动取消，不视为错误
        return null;
      }
      if (error.message === 'AUTH_ERROR') {
        throw new Error('认证已过期，请重新登录');
      }
      if (error.message === 'NETWORK_ERROR') {
        throw new Error('网络连接失败，请检查网络');
      }
      // Fetch 错误通常是网络问题
      throw new Error('服务不可用，请稍后再试');
    }
  })();

  return {
    bodyPromise: requestPromise,
    abort: () => abortController.abort(),
  };
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
 * LLM 端点配置管理
 */
export async function getEndpoints() {
  return apiClient.get(`${BASE_URL}/endpoints/`);
}

export async function addEndpoint(data) {
  return apiClient.post(`${BASE_URL}/endpoints/`, data);
}

export async function updateEndpoint(id, data) {
  return apiClient.put(`${BASE_URL}/endpoints/${id}/`, data);
}

export async function deleteEndpoint(id) {
  return apiClient.delete(`${BASE_URL}/endpoints/${id}/`);
}

export async function fetchEndpointModels(endpointId) {
  return apiClient.post(`${BASE_URL}/endpoints/${endpointId}/fetch-models/`);
}

export async function testEndpoint(endpointId) {
  return apiClient.post(`${BASE_URL}/endpoints/${endpointId}/test-endpoint/`);
}

/**
 * LLM 应用配置管理
 */
export async function getAppConfigs() {
  return apiClient.get(`${BASE_URL}/app-configs/`);
}

export async function addAppConfig(data) {
  return apiClient.post(`${BASE_URL}/app-configs/`, data);
}

export async function updateAppConfig(id, data) {
  return apiClient.put(`${BASE_URL}/app-configs/${id}/`, data);
}

export async function deleteAppConfig(id) {
  return apiClient.delete(`${BASE_URL}/app-configs/${id}/`);
}

/**
 * 旧版 LLM 配置管理（已废弃，保留向后兼容）
 */
export async function getLlmConfigs() {
  return apiClient.get(`${BASE_URL}/app-configs/`);
}

export async function addLlmConfig(data) {
  return apiClient.post(`${BASE_URL}/app-configs/`, data);
}

export async function updateLlmConfig(id, data) {
  return apiClient.put(`${BASE_URL}/app-configs/${id}/`, data);
}

export async function deleteLlmConfig(id) {
  return apiClient.delete(`${BASE_URL}/app-configs/${id}/`);
}

export async function fetchLlmModels(apiEndpoint, apiKey) {
  return apiClient.post(`${BASE_URL}/endpoints/fetch-models/`, {
    api_endpoint: apiEndpoint,
    api_key: apiKey,
  });
}

/**
 * Dify 应用管理
 */
export async function getDifyApps() {
  return apiClient.get('/api/dify-apps/');
}

export async function addDifyApp(data) {
  return apiClient.post('/api/dify-apps/', data);
}

export async function updateDifyApp(id, data) {
  return apiClient.put(`/api/dify-apps/${id}/`, data);
}

export async function deleteDifyApp(id) {
  return apiClient.delete(`/api/dify-apps/${id}/`);
}

/**
 * Ragflow 配置管理
 */
export async function getRagflowConfigs() {
  return apiClient.get('ragflow-service/configs/');
}

export async function addRagflowConfig(data) {
  return apiClient.post('ragflow-service/configs/', data);
}

export async function updateRagflowConfig(id, data) {
  return apiClient.put(`ragflow-service/configs/${id}/`, data);
}

export async function deleteRagflowConfig(id) {
  return apiClient.delete(`ragflow-service/configs/${id}/`);
}

/**
 * 统计接口
 */
export async function getStatsOverview(days = 30) {
  return apiClient.get(`${BASE_URL}/stats/overview/`, { params: { days } });
}

export async function getStatsDaily(days = 30) {
  return apiClient.get(`${BASE_URL}/stats/daily/`, { params: { days } });
}

/**
 * 知识库文档预览
 */
export async function previewDocument(docId) {
  return apiClient.get(`${BASE_URL}/knowledge-base/documents/${docId}/preview/`);
}

/**
 * 获取知识库文档分类列表
 */
export async function getDocCategories() {
  return apiClient.get(`${BASE_URL}/knowledge-base/documents/categories/`);
}

/**
 * 按分类获取知识库文档
 */
export async function getKnowledgeDocsByCategory(category) {
  return apiClient.get(`${BASE_URL}/knowledge-base/documents/`, { params: { category } });
}
