import apiClient from '../../../api/apiClient';

const complianceApi = {
    getAllComplianceIssues: (params) => apiClient.get('/compliance/', { params }),
    getComplianceIssueById: (id) => apiClient.get(`/compliance/${id}/`),
    createComplianceIssue: (issueData) => apiClient.post('/compliance/', issueData),
    updateComplianceIssue: (id, issueData) => apiClient.put(`/compliance/${id}/`, issueData),
    partialUpdateComplianceIssue: (id, issueData) => apiClient.patch(`/compliance/${id}/`, issueData),
    deleteComplianceIssue: (id) => apiClient.delete(`/compliance/${id}/`),
    getUnreadCount: () => apiClient.get('/compliance/unread_count/'), // 新增方法
};

export default complianceApi;