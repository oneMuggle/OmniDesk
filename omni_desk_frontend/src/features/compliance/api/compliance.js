import apiClient from '../../../shared/api/apiClient';

const complianceApi = {
    getAllComplianceIssues: (params) => apiClient.get('/api/compliance/', { params }),
    getComplianceIssueById: (id) => apiClient.get(`/api/compliance/${id}/`),
    createComplianceIssue: (issueData) => apiClient.post('/api/compliance/', issueData),
    updateComplianceIssue: (id, issueData) => apiClient.put(`/api/compliance/${id}/`, issueData),
    partialUpdateComplianceIssue: (id, issueData) => apiClient.patch(`/api/compliance/${id}/`, issueData),
    deleteComplianceIssue: (id) => apiClient.delete(`/api/compliance/${id}/`),
    getUnreadCount: () => apiClient.get('/api/compliance/unread_count/'), // 新增方法
};

export default complianceApi;