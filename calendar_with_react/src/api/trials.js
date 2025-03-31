import axios from 'axios';
import { handleResponse, handleError } from './responseHandler';

// 保持与personnel/equipment管理一致的axios配置
const api = axios.create({
  baseURL: (process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000') + '/api/events/',
  headers: {
    'Content-Type': 'application/json'
  }
});

// 统一认证拦截器
api.interceptors.request.use(config => {
  try {
    const authTokens = localStorage.getItem('authTokens');
    if (authTokens) {
      const tokens = JSON.parse(authTokens);
      if (tokens?.access) {
        config.headers.Authorization = `Bearer ${tokens.access}`;
      }
    }
  } catch (error) {
    console.error('Token解析错误:', error);
    localStorage.removeItem('authTokens');
  }
  return config;
});

// 试验管理API（与后端trials端点保持一致）
// 获取试验列表（与后端接口保持一致）
export const getTrials = (params) => {
  return api.get('/trials/', { params })
    .then(handleResponse)
    .catch(handleError);
};

// 保持原fetchTrials别名以兼容现有代码
export const fetchTrials = getTrials;

export const createTrial = (data) => {
  return api.post('/trials/', {
    ...data,
    equipments: data.related_equipment // 将前端字段名映射到后端API字段
  })
    .then(handleResponse)
    .catch(handleError);
};

export const updateTrial = (id, data) => {
  return api.patch(`/trials/${id}/`, {
    ...data,
    equipment: data.related_equipment // 保持字段映射一致性
  })
    .then(handleResponse)
    .catch(handleError);
};

export const deleteTrial = (id) => {
  return api.delete(`/trials/${id}/`)
    .then(handleResponse)
    .catch(handleError);
};

// 获取关联资源（与设备/人员管理一致）
// 设备列表接口（保持命名一致性）
export const getEquipmentOptions = async (params) => {
  console.log('[MCP_DEBUG] 正在请求设备选项数据...');
  const response = await api.get('/equipments/', { params })
    .catch(err => {
      console.error('[MCP_ERROR] 设备选项请求失败:', err.response?.data || err.message);
      throw err;
    });
  console.log('[MCP_DEBUG] 设备选项响应:', JSON.stringify(response.data, null, 2));
  return {
    results: response.data.results.map(item => ({
      id: item.id,
      name: item.name,
      description: item.description,
      serial_number: item.serial_number
    })),
    count: response.data.count
  };
};

export const getPersonnelOptions = async (params) => {
  console.log('[MCP_DEBUG] 正在请求人员选项数据...');
  const response = await api.get('/personnel/', { params })
    .catch(err => {
      console.error('[MCP_ERROR] 人员选项请求失败:', err.response?.data || err.message);
      throw err;
    });
  console.log('[MCP_DEBUG] 人员选项响应:', JSON.stringify(response.data, null, 2));
  return {
    results: response.data.results.map(person => ({
      id: person.id,
      name: person.name,
      department: person.department,
      phone: person.phone
    })),
    count: response.data.count
  };
};

// 试验状态选项（参照设备状态管理）
export const TRIAL_STATUS_OPTIONS = [
  { value: 'planned', label: '计划中' },
  { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'cancelled', label: '已取消' }
];
