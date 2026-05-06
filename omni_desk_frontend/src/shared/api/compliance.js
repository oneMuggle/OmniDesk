import apiClient from './axiosConfig';

export function getAllComplianceIssues(params = {}) {
  return apiClient.get('/api/compliance/', { params });
}

export function createComplianceIssue(data) {
  return apiClient.post('/api/compliance/', data);
}

export function updateComplianceIssue(id, data) {
  return apiClient.put(`/api/compliance/${id}/`, data);
}

export function deleteComplianceIssue(id) {
  return apiClient.delete(`/api/compliance/${id}/`);
}

export function getComplianceIssue(id) {
  return apiClient.get(`/api/compliance/${id}/`);
}

export default {
  getAllComplianceIssues,
  createComplianceIssue,
  updateComplianceIssue,
  deleteComplianceIssue,
  getComplianceIssue,
};
