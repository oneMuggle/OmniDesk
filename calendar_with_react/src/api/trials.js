import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`
  }
});

export const getTrials = () => api.get('/experiments/');
export const createTrial = (data) => api.post('/experiments/', data);
export const updateTrial = (id, data) => api.put(`/experiments/${id}/`, data);
export const deleteTrial = (id) => api.delete(`/experiments/${id}/`);
export const getEquipmentList = () => api.get('/equipments/');
export const getResponsiblePersons = () => api.get('/responsible-persons/');
