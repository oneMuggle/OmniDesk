import {
  getSensors,
  createSensor,
  updateSensor,
  deleteSensor,
  getCalibrationRecords,
  getCalibrationRecord,
  createCalibrationRecord,
  updateCalibrationRecord,
  deleteCalibrationRecord,
  getSensorCategories,
  createSensorCategory,
  updateSensorCategory,
  deleteSensorCategory,
  getStorageLocations,
  createStorageLocation,
  updateStorageLocation,
  deleteStorageLocation,
} from './sensorApi';
import apiClient from '../../../shared/api/apiClient';

jest.mock('../../../shared/api/apiClient', () => ({
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
}));

describe('sensorApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Sensors', () => {
    it('should get all sensors', async () => {
      const mockData = { data: { results: [{ id: 1, name: 'Sensor A' }] } };
      apiClient.get.mockResolvedValue(mockData);

      const result = await getSensors();

      expect(apiClient.get).toHaveBeenCalledWith('sensor-management/sensors/');
      expect(result).toEqual(mockData);
    });

    it('should create a sensor', async () => {
      const newSensor = { name: 'New Sensor', category: 1 };
      apiClient.post.mockResolvedValue({ data: { id: 1, ...newSensor } });

      const result = await createSensor(newSensor);

      expect(apiClient.post).toHaveBeenCalledWith('sensor-management/sensors/', newSensor);
      expect(result.data.name).toBe('New Sensor');
    });

    it('should update a sensor', async () => {
      const updatedData = { name: 'Updated Sensor' };
      apiClient.put.mockResolvedValue({ data: { id: 1, ...updatedData } });

      const result = await updateSensor(1, updatedData);

      expect(apiClient.put).toHaveBeenCalledWith('sensor-management/sensors/1/', updatedData);
      expect(result.data.id).toBe(1);
    });

    it('should delete a sensor', async () => {
      apiClient.delete.mockResolvedValue({});

      await deleteSensor(1);

      expect(apiClient.delete).toHaveBeenCalledWith('sensor-management/sensors/1/');
    });
  });

  describe('Calibration Records', () => {
    it('should get calibration records with params', async () => {
      const mockData = { data: { results: [{ id: 1, sensor_id: 1, calibration_date: '2024-01-01' }] } };
      apiClient.get.mockResolvedValue(mockData);

      const result = await getCalibrationRecords({ sensor_id: 1 });

      expect(apiClient.get).toHaveBeenCalledWith('sensor-management/sensor-calibrations/', { params: { sensor_id: 1 } });
      expect(result).toEqual(mockData);
    });

    it('should get single calibration record', async () => {
      apiClient.get.mockResolvedValue({ data: { id: 1, sensor_id: 1 } });

      const result = await getCalibrationRecord(1);

      expect(apiClient.get).toHaveBeenCalledWith('sensor-management/sensor-calibrations/1/');
      expect(result.data.id).toBe(1);
    });

    it('should create a calibration record', async () => {
      const recordData = { sensor_id: 1, calibration_date: '2024-01-01', result: 'pass' };
      apiClient.post.mockResolvedValue({ data: { id: 1, ...recordData } });

      const result = await createCalibrationRecord(recordData);

      expect(apiClient.post).toHaveBeenCalledWith('sensor-management/sensor-calibrations/', recordData);
      expect(result.data.result).toBe('pass');
    });

    it('should update a calibration record', async () => {
      const updateData = { result: 'fail' };
      apiClient.put.mockResolvedValue({ data: { id: 1, ...updateData } });

      await updateCalibrationRecord(1, updateData);

      expect(apiClient.put).toHaveBeenCalledWith('sensor-management/sensor-calibrations/1/', updateData);
    });

    it('should delete a calibration record', async () => {
      apiClient.delete.mockResolvedValue({});

      await deleteCalibrationRecord(1);

      expect(apiClient.delete).toHaveBeenCalledWith('sensor-management/sensor-calibrations/1/');
    });
  });

  describe('Sensor Categories', () => {
    it('should get all categories', async () => {
      apiClient.get.mockResolvedValue({ data: { results: [{ id: 1, name: 'Temperature' }] } });

      await getSensorCategories();

      expect(apiClient.get).toHaveBeenCalledWith('categories/', { params: undefined });
    });

    it('should create a category', async () => {
      apiClient.post.mockResolvedValue({ data: { id: 1, name: 'Humidity' } });

      await createSensorCategory({ name: 'Humidity' });

      expect(apiClient.post).toHaveBeenCalledWith('categories/', { name: 'Humidity' });
    });

    it('should update a category', async () => {
      apiClient.put.mockResolvedValue({ data: { id: 1, name: 'Updated' } });

      await updateSensorCategory(1, { name: 'Updated' });

      expect(apiClient.put).toHaveBeenCalledWith('categories/1/', { name: 'Updated' });
    });

    it('should delete a category', async () => {
      apiClient.delete.mockResolvedValue({});

      await deleteSensorCategory(1);

      expect(apiClient.delete).toHaveBeenCalledWith('categories/1/');
    });
  });

  describe('Storage Locations', () => {
    it('should get storage locations', async () => {
      apiClient.get.mockResolvedValue({ data: { results: [{ id: 1, name: 'Warehouse A' }] } });

      await getStorageLocations();

      expect(apiClient.get).toHaveBeenCalledWith('storage-locations/', { params: undefined });
    });

    it('should create a storage location', async () => {
      apiClient.post.mockResolvedValue({ data: { id: 1, name: 'New Location' } });

      await createStorageLocation({ name: 'New Location' });

      expect(apiClient.post).toHaveBeenCalledWith('storage-locations/', { name: 'New Location' });
    });

    it('should update a storage location', async () => {
      apiClient.put.mockResolvedValue({ data: { id: 1, name: 'Updated Location' } });

      await updateStorageLocation(1, { name: 'Updated Location' });

      expect(apiClient.put).toHaveBeenCalledWith('storage-locations/1/', { name: 'Updated Location' });
    });

    it('should delete a storage location', async () => {
      apiClient.delete.mockResolvedValue({});

      await deleteStorageLocation(1);

      expect(apiClient.delete).toHaveBeenCalledWith('storage-locations/1/');
    });
  });
});
