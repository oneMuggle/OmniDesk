import apiClient from './apiClient';

export const getPersonnel = async (params) => {
  const response = await apiClient.get('/users/personnel/', { params });
  return response.data;
};

// 新增函数，用于获取所有人员信息
export const getAllPersonnel = async () => {
  const response = await apiClient.get('/users/personnel/all/');
  return response.data;
};

export const getPersonnelDetails = (id) => {
  return apiClient.get(`/users/personnel/${id}/`);
};

export const createPersonnel = (data) => {
  return apiClient.post('/users/personnel/', data);
};

export const updatePersonnel = (id, data) => {
  return apiClient.put(`/users/personnel/${id}/`, data);
};

export const deletePersonnel = (id) => {
  const url = `/users/personnel/${id}/`;
  return apiClient.delete(url);
};

export const getPositions = async () => {
  const response = await apiClient.get('/users/positions/');
  return response.data;
};

export const createPosition = (data) => {
  return apiClient.post('/users/positions/', data);
};

export const updatePosition = (id, data) => {
  return apiClient.put(`/users/positions/${id}/`, data);
};

export const deletePosition = (id) => {
  return apiClient.delete(`/users/positions/${id}/`);
};
