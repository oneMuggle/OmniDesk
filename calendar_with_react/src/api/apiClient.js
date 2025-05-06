import axios from 'axios';

// 创建可配置的axios实例
export const createApiClient = (options = {}) => {
  return axios.create({
    baseURL: process.env.NODE_ENV === 'production' ? '/api' : (process.env.REACT_APP_API_BASE_URL ? `${process.env.REACT_APP_API_BASE_URL}/api` : 'http://localhost:8000/api'),
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest'
    },
    withCredentials: !options.skipAuth,
    xsrfCookieName: 'csrftoken',
    xsrfHeaderName: 'X-CSRFToken'
  });
};

// 默认实例（保持向后兼容）
export const apiClient = createApiClient();

export default apiClient;
