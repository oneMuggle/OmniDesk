import axios from 'axios';

const CATEGORY_API_URL = '/api/sensor-management/categories/';
const STORAGE_LOCATION_API_URL = '/api/sensor-management/storage-locations/';

// --- Sensor Category API ---

// 获取所有传感器类别
export const getSensorCategories = () => {
  return axios.get(CATEGORY_API_URL);
};

// 创建新的传感器类别
export const createSensorCategory = (category) => {
  return axios.post(CATEGORY_API_URL, category);
};

// 更新现有的传感器类别
export const updateSensorCategory = (id, category) => {
  return axios.put(`${CATEGORY_API_URL}${id}/`, category);
};

// 删除传感器类别
export const deleteSensorCategory = (id) => {
  return axios.delete(`${CATEGORY_API_URL}${id}/`);
};

// --- Storage Location API ---

// 获取所有存放地点
export const getStorageLocations = () => {
  return axios.get(STORAGE_LOCATION_API_URL);
};

// 创建新的存放地点
export const createStorageLocation = (location) => {
  return axios.post(STORAGE_LOCATION_API_URL, location);
};

// 更新现有的存放地点
export const updateStorageLocation = (id, location) => {
  return axios.put(`${STORAGE_LOCATION_API_URL}${id}/`, location);
};

// 删除存放地点
export const deleteStorageLocation = (id) => {
  return axios.delete(`${STORAGE_LOCATION_API_URL}${id}/`);
};