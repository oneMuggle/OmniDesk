import { apiClient } from './personnel';

export const getEquipment = async (params = {}) => {
  try {
    const response = await apiClient.get('/events/equipment/', {
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
      window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
      return;
    }
    throw error.response.data;
  }
};

export const createEquipment = async (data) => {
  try {
    const response = await apiClient.post('/events/equipment/', data);
    return response.data;
  } catch (error) {
    if (error.response?.status === 401) {
      window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
      return;
    }
    throw error.response?.data || { message: '创建设备信息失败' };
  }
};

export const updateEquipment = async (id, data) => {
  try {
    const response = await apiClient.patch(`/events/equipment/${id}/`, data);
    return response.data;
  } catch (error) {
    if (error.response?.status === 401) {
      window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
      return;
    }
    throw error.response?.data || { message: '更新设备信息失败' };
  }
};

export const deleteEquipment = async (id) => {
  try {
    await apiClient.delete(`/events/equipment/${id}/`);
    return { success: true };
  } catch (error) {
    if (error.response?.status === 401) {
      window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
      return;
    }
    throw error.response?.data || { message: '删除设备信息失败' };
  }
};
