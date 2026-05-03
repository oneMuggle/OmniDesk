import apiClient from '../../shared/api/apiClient';

const BASE_URL = '/smart-assistant';

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
