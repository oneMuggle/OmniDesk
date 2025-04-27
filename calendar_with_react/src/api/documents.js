import axios from 'axios';

const API_URL = process.env.REACT_APP_API_BASE_URL;

export const documentAPI = {
  uploadTemplate: (formData) => axios.post(`${API_URL}/templates`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
      Authorization: `Bearer ${localStorage.getItem('token')}`
    }
  }),

  generateDocument: (templateId, data) => axios.post(`${API_URL}/generate/${templateId}`, data, {
    responseType: 'blob',
    headers: {
      Authorization: `Bearer ${localStorage.getItem('token')}`
    }
  }),
  
  saveResponsibles: (responsibles) => axios.post(`${API_URL}/responsibles/`, responsibles, {
    headers: {
      Authorization: `Bearer ${localStorage.getItem('token')}`
    }
  }),
  
  analyzeFile: (formData) => axios.post(`${API_URL}/templates/analyze`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
      Authorization: `Bearer ${localStorage.getItem('token')}`
    }
  })
};
