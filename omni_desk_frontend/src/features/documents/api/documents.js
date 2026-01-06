import apiClient from '../../../shared/api/apiClient'; // 统一使用 apiClient

const documentsApi = {
  // 获取文档模板列表，支持按项目ID筛选
  getDocumentTemplates: (projectId = null) => {
    let url = `documents/templates/`;
    if (projectId) {
      url += `?project_id=${projectId}`;
    }
    return apiClient.get(url);
  },

  // 上传新模板
  uploadTemplate: (formData) => {
    return apiClient.post('documents/templates/upload/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  // 分析指定的文档模板
  analyzeDocumentTemplate: (templateId) => {
    return apiClient.post(`documents/templates/${templateId}/analyze/`);
  },

  // （保留）基于模板生成文档
  generateDocument: (templateId, data) => {
    return apiClient.post(`documents/generate/${templateId}`, data, {
      responseType: 'blob',
    });
  },
};

export default documentsApi;