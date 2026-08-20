import client from './client';

export const listReports = (params) => client.get('reports/', { params });
export const getReport = (id) => client.get(`reports/${id}/`);
export const createReport = (data) => client.post('reports/', data);
export const updateReport = (id, data) => client.patch(`reports/${id}/`, data);
export const submitReport = (id) => client.post(`reports/${id}/submit/`);
export const approveReport = (id) => client.post(`reports/${id}/approve/`);
export const rejectReport = (id, reviewerComment) =>
  client.post(`reports/${id}/reject/`, { reviewer_comment: reviewerComment });
