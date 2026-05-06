import apiClient from '../../../shared/api/apiClient';

// 获取所有传感器列表
export const getSensors = () => {
  return apiClient.get('sensor-management/sensors/');
};

// 创建一个新传感器
export const createSensor = (data) => {
  return apiClient.post('sensor-management/sensors/', data);
};
// 更新现有传感器的信息
export const updateSensor = (id, data) => {
  return apiClient.put(`sensor-management/sensors/${id}/`, data);
};

// 删除一个传感器
export const deleteSensor = (id) => {
  return apiClient.delete(`sensor-management/sensors/${id}/`);
};


// 获取校准记录列表
export const getCalibrationRecords = (params) => {
  return apiClient.get('sensor-management/sensor-calibrations/', { params });
};

// 获取单个校准记录详情
export const getCalibrationRecord = (id) => {
  return apiClient.get(`sensor-management/sensor-calibrations/${id}/`);
};

// 创建一条新的校准记录
export const createCalibrationRecord = (data) => {
  return apiClient.post('sensor-management/sensor-calibrations/', data);
};

// 更新校准记录
export const updateCalibrationRecord = (id, data) => {
  return apiClient.put(`sensor-management/sensor-calibrations/${id}/`, data);
};

// 删除校准记录
export const deleteCalibrationRecord = (id) => {
  return apiClient.delete(`sensor-management/sensor-calibrations/${id}/`);
};

// SensorCategory API
export const getSensorCategories = (params) => {
  return apiClient.get('categories/', { params });
};

export const createSensorCategory = (data) => {
  return apiClient.post('categories/', data);
};

export const updateSensorCategory = (id, data) => {
  return apiClient.put(`categories/${id}/`, data);
};

export const deleteSensorCategory = (id) => {
  return apiClient.delete(`categories/${id}/`);
};

// StorageLocation API
export const getStorageLocations = (params) => {
  return apiClient.get('storage-locations/', { params });
};

export const createStorageLocation = (data) => {
  return apiClient.post('storage-locations/', data);
};

export const updateStorageLocation = (id, data) => {
  return apiClient.put(`storage-locations/${id}/`, data);
};

export const deleteStorageLocation = (id) => {
  return apiClient.delete(`storage-locations/${id}/`);
};