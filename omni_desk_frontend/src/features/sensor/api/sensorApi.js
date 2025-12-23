import apiClient from '../../../shared/api/apiClient';

// 获取所有传感器列表
export const getSensors = () => {
  return apiClient.get('/api/sensor-management/sensors/');
};

// 创建一个新传感器
export const createSensor = (data) => {
  return apiClient.post('/api/sensor-management/sensors/', data);
};
// 更新现有传感器的信息
export const updateSensor = (id, data) => {
  return apiClient.put(`/api/sensor-management/sensors/${id}/`, data);
};

// 删除一个传感器
export const deleteSensor = (id) => {
  return apiClient.delete(`/api/sensor-management/sensors/${id}/`);
};


// 根据参数获取校准记录列表
export const getCalibrationRecords = (params) => {
  return apiClient.get('/api/calibration-records/', { params });
};

// 创建一条新的校准记录
export const createCalibrationRecord = (data) => {
  return apiClient.post('/api/calibration-records/', data);
};

// SensorCategory API
export const getSensorCategories = () => {
  return apiClient.get('/api/sensor-management/categories/');
};

export const createSensorCategory = (data) => {
  return apiClient.post('/api/sensor-management/categories/', data);
};

export const updateSensorCategory = (id, data) => {
  return apiClient.put(`/api/sensor-management/categories/${id}/`, data);
};

export const deleteSensorCategory = (id) => {
  return apiClient.delete(`/api/sensor-management/categories/${id}/`);
};

// StorageLocation API
export const getStorageLocations = () => {
  return apiClient.get('/api/sensor-management/storage-locations/');
};

export const createStorageLocation = (data) => {
  return apiClient.post('/api/sensor-management/storage-locations/', data);
};

export const updateStorageLocation = (id, data) => {
  return apiClient.put(`/api/sensor-management/storage-locations/${id}/`, data);
};

export const deleteStorageLocation = (id) => {
  return apiClient.delete(`/api/sensor-management/storage-locations/${id}/`);
};