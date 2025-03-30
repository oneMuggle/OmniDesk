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
  return api.post('/trials/', data)
    .then(handleResponse)
    .catch(handleError);
};

export const updateTrial = (id, data) => {
  return api.patch(`/trials/${id}/`, data)
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
export const getEquipmentList = () => api.get('/equipments/');
export const getEquipmentOptions = getEquipmentList; // 保持原有导出以兼容

// 负责人列表接口（保持命名一致性）
export const getResponsiblePersons = () => api.get('/responsible-persons/');
export const getPersonnelOptions = getResponsiblePersons; // 保持原有导出以兼容

// 试验状态选项（参照设备状态管理）
export const TRIAL_STATUS_OPTIONS = [
  { value: 'planned', label: '计划中' },
  { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'cancelled', label: '已取消' }
];
