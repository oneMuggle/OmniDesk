import api from './axiosConfig';

const API_BASE = '/file';

export const fileProcessingApi = {
  /**
   * 上传文件
   * @param {File} file - 文件对象
   * @returns {Promise<{id: string, status: string}>}
   */
  upload: async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post(`${API_BASE}/upload/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });

    return response.data;
  },

  /**
   * 获取文件预览数据
   * @param {string} fileId - 文件 ID
   * @returns {Promise<Object>}
   */
  getPreview: async (fileId) => {
    const response = await api.get(`${API_BASE}/${fileId}/preview/`);
    return response.data;
  },

  /**
   * AI 数据分析
   * @param {string} fileId - 文件 ID
   * @returns {Promise<Object>}
   */
  analyze: async (fileId) => {
    const response = await api.post(`${API_BASE}/${fileId}/analyze/`);
    return response.data;
  },

  /**
   * 自然语言查询
   * @param {string} fileId - 文件 ID
   * @param {string} question - 用户问题
   * @returns {Promise<{analysis_id: string, question: string, answer: string}>}
   */
  query: async (fileId, question) => {
    const response = await api.post(`${API_BASE}/${fileId}/query/`, { question });
    return response.data;
  },

  /**
   * 导出文件
   * @param {string} fileId - 文件 ID
   * @param {string} format - 导出格式 (csv|markdown|excel)
   * @returns {Promise<Blob>}
   */
  export: async (fileId, format) => {
    const response = await api.get(`${API_BASE}/${fileId}/export/${format}/`, {
      responseType: 'blob',
    });
    return response.data;
  },
};
