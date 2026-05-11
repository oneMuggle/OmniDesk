import axiosInstance from '../../shared/api/axiosConfig';

const BASE_URL = '/external/plugins/';

export const fetchPlugins = async (params = {}) => {
  const response = await axiosInstance.get(BASE_URL, { params });
  return response.data;
};

export const fetchPluginDetail = async (id) => {
  const response = await axiosInstance.get(`${BASE_URL}${id}/`);
  return response.data;
};

export const uploadPluginVersion = async (pluginId, formData) => {
  const response = await axiosInstance.post(
    `${BASE_URL}${pluginId}/upload_version/`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return response.data;
};

export const executePlugin = async (pluginId, params = {}) => {
  const response = await axiosInstance.post(`${BASE_URL}${pluginId}/execute/`, { params });
  return response.data;
};

export const reviewPlugin = async (pluginId, action, notes = '') => {
  const response = await axiosInstance.post(`${BASE_URL}${pluginId}/review/`, { action, notes });
  return response.data;
};

export const fetchPluginLogs = async (pluginId, params = {}) => {
  const response = await axiosInstance.get(`${BASE_URL}${pluginId}/logs/`, { params });
  return response.data;
};

export const fetchPluginTemplates = async () => {
  const response = await axiosInstance.get('/external/plugin-templates/');
  return response.data;
};

export const createPlugin = async (data) => {
  const response = await axiosInstance.post(BASE_URL, data);
  return response.data;
};

export const updatePlugin = async (id, data) => {
  const response = await axiosInstance.patch(`${BASE_URL}${id}/`, data);
  return response.data;
};

export const deletePlugin = async (id) => {
  const response = await axiosInstance.delete(`${BASE_URL}${id}/`);
  return response.data;
};
