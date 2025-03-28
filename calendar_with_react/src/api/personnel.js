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

export const getPersonnel = async (params = {}) => {
  try {
    const response = await apiClient.get('/events/personnel/', {
      params: {
        page: params.page,
        page_size: params.pageSize
      }
    });
    
    return {
      data: response.data.results || [],
      pagination: {
        current: response.data.current_page || 1,
        total: response.data.count || 0,
        pageSize: response.data.page_size || 10
      }
    };
  } catch (error) {
    if (!error.response) {
      throw { message: '网络连接异常，请检查网络后重试' };
    }
    if (error.response.status === 401) {
      // 触发重新认证流程
      window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
      return;
    }
    throw error.response.data;
  }
};

export const createPerson = async (data) => {
  try {
    const response = await apiClient.post('/events/personnel/', data);
    return response.data;
  } catch (error) {
    if (error.response?.status === 401) {
      window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
      return;
    }
    throw error.response?.data || { message: '创建人员信息失败' };
  }
};

export const updatePerson = async (id, data) => {
  try {
    const response = await apiClient.patch(`/events/personnel/${id}/`, data);
    return response.data;
  } catch (error) {
    if (error.response?.status === 401) {
      window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
      return;
    }
    throw error.response?.data || { message: '更新人员信息失败' };
  }
};

export const deletePerson = async (id) => {
  try {
    await apiClient.delete(`/events/personnel/${id}/`);
    return { success: true };
  } catch (error) {
    if (error.response?.status === 401) {
      window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
      return;
    }
    throw error.response?.data || { message: '删除人员信息失败' };
  }
};
