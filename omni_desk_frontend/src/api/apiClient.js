import axios from 'axios';

const getCookie = (name) => {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
};

// 创建可配置的axios实例
export const createApiClient = (options = {}) => {
  const instance = axios.create({
    baseURL: process.env.NODE_ENV === 'production' ? '/api' : (process.env.REACT_APP_API_BASE_URL ? `${process.env.REACT_APP_API_BASE_URL}/api` : 'http://localhost:8000/api'),
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest'
    },
    withCredentials: !options.skipAuth,
  });

  instance.interceptors.request.use(config => {
    // For methods that can cause side-effects, attach the CSRF token.
    if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(config.method.toUpperCase())) {
        const csrfToken = getCookie('csrftoken');
        if (csrfToken) {
          config.headers['X-CSRFToken'] = csrfToken;
        }
    }
    return config;
  }, error => {
    return Promise.reject(error);
  });

  return instance;
};

// 默认实例（保持向后兼容）
export const apiClient = createApiClient();

export default apiClient;
