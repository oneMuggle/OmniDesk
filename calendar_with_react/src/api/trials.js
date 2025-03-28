import axios from 'axios';

const api = axios.create({
  baseURL: (process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000') + '/api/experiments/',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`
  }
});

export const getTrials = () => api.get('/experiments/');
export const createTrial = (data) => api.post('/experiments/', {
  ...data,
  equipments: data.equipments?.join(','),  // 将数组转换为逗号分隔字符串
  responsible_persons: data.responsible_persons?.join(',')
});

export const updateTrial = (id, data) => api.put(`/experiments/${id}/`, {
  ...data,
  equipments: data.equipments?.join(','),
  responsible_persons: data.responsible_persons?.join(',')
});
export const deleteTrial = (id) => api.delete(`/experiments/${id}/`);
export const getEquipmentList = () => api.get('/experiments/equipment/');
export const getResponsiblePersons = () => api.get('/experiments/personnel/');
