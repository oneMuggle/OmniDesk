import apiClient from './apiClient';

export const getPersonnel = () => {
  return apiClient.get('/events/personnel/');
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
