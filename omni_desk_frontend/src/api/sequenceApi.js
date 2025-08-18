import apiClient from './apiClient';

// ================== Personnel Sequence ==================

// 获取所有人员顺序
export const getPersonnelSequences = () => {
  return apiClient.get('/events/personnel-sequences/');
};

// 获取单个人员顺序
export const getPersonnelSequenceDetails = (id) => {
  return apiClient.get(`/personnel-sequences/${id}/`);
};

// 创建人员顺序
export const createPersonnelSequence = (data) => {
  return apiClient.post('/personnel-sequences/', data);
};

// 更新人员顺序
export const updatePersonnelSequence = (id, data) => {
  return apiClient.put(`/personnel-sequences/${id}/`, data);
};

// 删除人员顺序
export const deletePersonnelSequence = (id) => {
  return apiClient.delete(`/personnel-sequences/${id}/`);
};


// ================== Leader Sequence ==================

// 获取所有领导顺序
export const getLeaderSequences = () => {
  return apiClient.get('/events/leader-sequences/');
};

// 获取单个领导顺序
export const getLeaderSequenceDetails = (id) => {
  return apiClient.get(`/leader-sequences/${id}/`);
};

// 创建领导顺序
export const createLeaderSequence = (data) => {
  return apiClient.post('/leader-sequences/', data);
};

// 更新领导顺序
export const updateLeaderSequence = (id, data) => {
  return apiClient.put(`/leader-sequences/${id}/`, data);
};

// 删除领导顺序
export const deleteLeaderSequence = (id) => {
  return apiClient.delete(`/leader-sequences/${id}/`);
};