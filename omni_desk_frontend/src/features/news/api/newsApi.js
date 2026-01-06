import apiClient from '../../../shared/api/apiClient';

// NewsType API
export const getNewsTypes = () => {
  return apiClient.get('news-types/');
};

export const createNewsType = (data) => {
  return apiClient.post('news-types/', data);
};

export const updateNewsType = (id, data) => {
  return apiClient.put(`news-types/${id}/`, data);
};

export const deleteNewsType = (id) => {
  return apiClient.delete(`news-types/${id}/`);
};

// NewsArticle API
export const getNewsArticles = (params) => {
  return apiClient.get('news-articles/', { params });
};

export const createNewsArticle = (data) => {
  return apiClient.post('news-articles/', data);
};

export const updateNewsArticle = (id, data) => {
  return apiClient.put(`news-articles/${id}/`, data);
};

export const deleteNewsArticle = (id) => {
  return apiClient.delete(`news-articles/${id}/`);
};

// NewsStats API
export const getNewsStats = () => {
  return apiClient.get('news-stats/');
};