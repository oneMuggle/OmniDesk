import axios from 'axios';

// 配置axios实例
export const apiClient = axios.create({
  baseURL: (process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000') + '/api/'
});

// 添加请求拦截器
apiClient.interceptors.request.use(config => {
  // 确保正确处理认证令牌
  try {
    const authTokens = localStorage.getItem('authTokens');
    if (authTokens) {
      const { access } = JSON.parse(authTokens);
      if (access) {
        config.headers.Authorization = `Bearer ${access}`;
        console.log('Using JWT token:', access.substring(0, 20) + '...');
        return config;
      } else {
        console.error('Access token missing in authTokens');
        localStorage.removeItem('authTokens');
      }
    }
  } catch (error) {
    console.error('Error parsing authTokens:', error);
  }
  
  console.warn('No valid JWT token available');
  // 触发重新认证流程
  if (!window.location.pathname.includes('/login')) {
    window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
  }
  return config;
});

export const getPersonnel = async () => {
  try {
    const response = await apiClient.get('/events/personnel/');
    return Array.isArray(response.data) ? response.data : [];
  } catch (error) {
    throw error.response.data;
  }
};

export const createPerson = async (data) => {
  try {
    const response = await apiClient.post('/events/personnel/', data);
    return response.data;
  } catch (error) {
    throw error.response.data;
  }
};

export const updatePerson = async (id, data) => {
  try {
    const response = await apiClient.put(`/events/personnel/${id}/`, data);
    return response.data;
  } catch (error) {
    throw error.response.data;
  }
};

export const deletePerson = async (id) => {
  try {
    const response = await apiClient.delete(`/events/personnel/${id}/`);
    return response.data;
  } catch (error) {
    throw error.response.data;
  }
};
