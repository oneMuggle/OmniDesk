import { apiClient } from '../context/AuthContext';
import { handleError } from './responseHandler';

// 辅助函数：验证和转换人员数据
const transformPersonnelData = (data) => {
  if (!data) return [];
  
  // 处理直接返回数组的情况
  if (Array.isArray(data)) {
    return data.map(person => ({
      id: person?.id || '',
      name: person?.name || '未知',
      phone: person?.phone || '',
      email: person?.email || '',
      role: person?.role || '',
      department: person?.department || ''
    }));
  }

  // 处理分页响应格式 (如 { results: [...] })
  if (Array.isArray(data.results)) {
    return data.results.map(person => ({
      id: person?.id || '',
      name: person?.name || '未知',
      phone: person?.phone || '',
      email: person?.email || '',
      role: person?.role || '',
      department: person?.department || ''
    }));
  }

  // 处理其他格式或记录警告
  console.warn('Unexpected personnel data structure:', data);
  return [];
};

export const personnelApi = {
  getPersonnel: async () => {
    try {
      const response = await apiClient.get('/api/events/personnel/');
      return transformPersonnelData(response.data);
    } catch (error) {
      // 增强错误信息
      if (error.response) {
        error.message = `获取人员数据失败: ${error.response.status} ${error.response.statusText}`;
        error.details = {
          responseData: error.response.data,
          requestUrl: error.config?.url
        };
      }
      handleError(error);
      throw error;
    }
  }
};
