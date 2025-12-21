import apiClient from '../../../shared/api/apiClient';

// 获取所有传感器列表
export const getSensors = () => {
  return apiClient.get('/sensor-management/sensors/');
};

// 创建一个新传感器
export const createSensor = (data) => {
  return apiClient.post('/sensor-management/sensors/', data);
};

// 根据参数获取校准记录列表
export const getCalibrationRecords = (params) => {
  return apiClient.get('/calibration-records/', { params });
};

// 创建一条新的校准记录
export const createCalibrationRecord = (data) => {
  return apiClient.post('/calibration-records/', data);
};