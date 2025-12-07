import apiClient from './apiClient';

// 获取所有传感器列表
export const getSensors = () => {
  return apiClient.get('/api/sensors/');
};

// 创建一个新传感器
export const createSensor = (data) => {
  return apiClient.post('/api/sensors/', data);
};

// 根据参数获取校准记录列表
export const getCalibrationRecords = (params) => {
  return apiClient.get('/api/calibration-records/', { params });
};

// 创建一条新的校准记录
export const createCalibrationRecord = (data) => {
  return apiClient.post('/api/calibration-records/', data);
};