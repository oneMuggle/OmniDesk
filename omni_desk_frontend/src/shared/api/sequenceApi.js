import apiClient from './apiClient';

// ================== Personnel Sequence ==================

// 获取所有人员顺序
export const getPersonnelSequences = () => {
  return apiClient.get('/api/events/personnel-sequences/');
};

// 获取单个人员顺序
export const getPersonnelSequenceDetails = (id) => {
  return apiClient.get(`/api/events/personnel-sequences/${id}/`);
};

// 创建人员顺序
export const createPersonnelSequence = (data) => {
  return apiClient.post('/api/events/personnel-sequences/', data);
};

// 更新人员顺序
export const updatePersonnelSequence = (id, data) => {
  return apiClient.put(`/api/events/personnel-sequences/${id}/`, data);
};

// 删除人员顺序
export const deletePersonnelSequence = (id) => {
  return apiClient.delete(`/api/events/personnel-sequences/${id}/`);
};


// ================== Leader Sequence ==================

// 获取所有领导顺序
export const getLeaderSequences = () => {
  return apiClient.get('/api/events/leader-sequences/');
};

// 获取单个领导顺序
export const getLeaderSequenceDetails = (id) => {
  return apiClient.get(`/api/events/leader-sequences/${id}/`);
};

// 创建领导顺序
export const createLeaderSequence = (data) => {
  return apiClient.post('/api/events/leader-sequences/', data);
};

// 更新领导顺序
export const updateLeaderSequence = (id, data) => {
  return apiClient.put(`/api/events/leader-sequences/${id}/`, data);
};

// 删除领导顺序
export const deleteLeaderSequence = (id) => {
  return apiClient.delete(`/api/events/leader-sequences/${id}/`);
};