import apiClient from './apiClient';

export const getPersonnel = async () => {
  const response = await apiClient.get('/events/personnel/');
  return response.data;
};

// 新增函数，用于获取所有人员信息
export const getAllPersonnel = async () => {
  const response = await apiClient.get('/events/personnel/all/');
  return response.data;
};

export const getPersonnelDetails = (id) => {
  return apiClient.get(`/events/personnel/${id}/`);
};

export const createPersonnel = (data) => {
  return apiClient.post('/events/personnel/', data);
};

export const updatePersonnel = (id, data) => {
  return apiClient.put(`/events/personnel/${id}/`, data);
};

export const deletePersonnel = (id) => {
  return apiClient.delete(`/events/personnel/${id}/`);
};
