import apiClient from '../../../shared/api/apiClient';

const BASE_URL = 'smart-assistant';

/**
 * 后端输出契约(format_version: 1):失败 kind → 前端友好提示映射。
 * 当事件未携带 hint 时,用此映射兜底;未知 kind 归入 internal_error。
 */
export const ERROR_KIND_MESSAGES = {
  no_llm_endpoint: '管理员尚未配置 LLM 服务，请前往「管理后台 → AI 应用」配置端点',
  llm_unavailable: 'LLM 服务暂时不可用，请稍后重试',
  ragflow_unavailable: '知识库服务暂时不可用，本次回答未包含知识库内容',
  rate_limited: '请求过于频繁，请稍后再试',
  internal_error: '服务异常，请稍后重试',
};

/**
 * 从 SSE done/session 事件(或同步失败响应)中解析辅助提示文案。
 *
 * 防御性兼容:后端分两步上线,kind/hint/error 字段可能尚未存在 —
 * - hint 优先于 kind 映射
 * - 有 kind 但未知 → internal_error 兜底
 * - 仅 error:true 无 kind/hint → internal_error 兜底
 * - 完全没有 kind/hint/error 字段(旧事件) → 返回 undefined,行为与旧版一致
 *
 * @param {object|undefined|null} event SSE 事件或失败响应对象
 * @returns {string|undefined} 辅助提示文案;无可提示内容时为 undefined
 */
export function resolveErrorHint(event) {
  if (!event) return undefined;
  const hint = typeof event.hint === 'string' && event.hint.trim() ? event.hint.trim() : undefined;
  if (hint) return hint;
  if (event.kind) {
    return ERROR_KIND_MESSAGES[event.kind] || ERROR_KIND_MESSAGES.internal_error;
  }
  if (event.error) return ERROR_KIND_MESSAGES.internal_error;
  return undefined;
}

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
 * 提交消息反馈（赞/踩）
 * PATCH /api/smart-assistant/agent-logs/{logId}/feedback/
 * @param {number|string} logId AgentLog ID（来自对话响应的 log_id 字段）
 * @param {'up'|'down'} feedback 反馈类型
 */
export async function submitFeedback(logId, feedback) {
  return apiClient.patch(`${BASE_URL}/agent-logs/${logId}/feedback/`, { feedback });
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
