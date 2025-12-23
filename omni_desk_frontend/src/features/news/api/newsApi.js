import apiClient from '../../../shared/api/apiClient';

// NewsType API
export const getNewsTypes = () => {
  return apiClient.get('/api/news-types/');
};

export const createNewsType = (data) => {
  return apiClient.post('/api/news-types/', data);
};

export const updateNewsType = (id, data) => {
  return apiClient.put(`/api/news-types/${id}/`, data);
};

export const deleteNewsType = (id) => {
  return apiClient.delete(`/api/news-types/${id}/`);
};

// NewsArticle API
export const getNewsArticles = (params) => {
  return apiClient.get('/api/news-articles/', { params });
};

export const createNewsArticle = (data) => {
  return apiClient.post('/api/news-articles/', data);
};

export const updateNewsArticle = (id, data) => {
  return apiClient.put(`/api/news-articles/${id}/`, data);
};

export const deleteNewsArticle = (id) => {
  return apiClient.delete(`/api/news-articles/${id}/`);
};

// NewsStats API
export const getNewsStats = () => {
  return apiClient.get('/api/news-stats/');
};