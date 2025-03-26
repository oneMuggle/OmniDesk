import axios from 'axios';

const API_URL = process.env.REACT_APP_API_BASE_URL + '/api/personnel/';

export const getPersonnel = async () => {
  try {
    const response = await axios.get(API_URL);
    return response.data;
  } catch (error) {
    throw error.response.data;
  }
};

export const createPerson = async (data) => {
  try {
    const response = await axios.post(API_URL, data);
    return response.data;
  } catch (error) {
    throw error.response.data;
  }
};

export const updatePerson = async (id, data) => {
  try {
    const response = await axios.put(`${API_URL}${id}/`, data);
    return response.data;
  } catch (error) {
    throw error.response.data;
  }
};

export const deletePerson = async (id) => {
  try {
    const response = await axios.delete(`${API_URL}${id}/`);
    return response.data;
  } catch (error) {
    throw error.response.data;
  }
};
