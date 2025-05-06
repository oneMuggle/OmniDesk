import axios from 'axios';

// 创建基础axios实例
export const apiClient = axios.create({
  baseURL: process.env.NODE_ENV === 'production' ? '/api' : (process.env.REACT_APP_API_BASE_URL ? `${process.env.REACT_APP_API_BASE_URL}/api` : 'http://localhost:8000/api'),
  headers: {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
  },
  withCredentials: true,
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken'
});

export default apiClient;
