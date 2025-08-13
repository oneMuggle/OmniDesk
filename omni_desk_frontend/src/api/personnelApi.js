import apiClient from './apiClient';

export const getPersonnel = () => {
  return apiClient.get('/personnel/');
};

export const getPersonnelDetails = (id) => {
  return apiClient.get(`/personnel/${id}/`);
};

export const createPersonnel = (data) => {
  return apiClient.post('/personnel/', data);
};

export const updatePersonnel = (id, data) => {
  return apiClient.put(`/personnel/${id}/`, data);
};

export const deletePersonnel = (id) => {
  return apiClient.delete(`/personnel/${id}/`);
};
