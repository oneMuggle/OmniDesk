import apiClient from './apiClient';

export const getPersonnel = async (params) => {
  const response = await apiClient.get('/personnel/personnel/', { params });
  return response.data;
};

// 新增函数，用于获取所有人员信息
export const getAllPersonnel = async () => {
  // To get all personnel, we call the list endpoint with a large page size.
  const response = await apiClient.get('/personnel/personnel/', { params: { page_size: 1000 } });
  return response.data.results; // DRF paginated response returns results in a 'results' key
};

export const getPersonnelDetails = (id) => {
  return apiClient.get(`/personnel/personnel/${id}/`);
};

export const createPersonnel = (data) => {
  return apiClient.post('/personnel/personnel/', data);
};

export const updatePersonnel = (id, data) => {
  return apiClient.put(`/personnel/personnel/${id}/`, data);
};

export const deletePersonnel = (id) => {
  const url = `/personnel/personnel/${id}/`;
  return apiClient.delete(url);
};

export const getPositions = async () => {
  const response = await apiClient.get('/events/positions/');
  return response.data;
};

export const createPosition = (data) => {
  return apiClient.post('/personnel/positions/', data);
};

export const updatePosition = (id, data) => {
  return apiClient.put(`/personnel/positions/${id}/`, data);
};

export const deletePosition = (id) => {
  return apiClient.delete(`/personnel/positions/${id}/`);
};
