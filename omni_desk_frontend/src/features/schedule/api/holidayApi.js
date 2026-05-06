import apiClient from '../../../shared/api/apiClient';
import { handleError } from '../../../shared/api/responseHandler';

export const holidayApi = {
  getHolidays: async (year) => {
    try {
      const params = year ? { year } : {};
      const response = await apiClient.get('events/holidays/', { params });
      return response.data.results || [];
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  createHoliday: async (holidayData) => {
    try {
      const response = await apiClient.post('events/holidays/', holidayData);
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  updateHoliday: async (holidayId, holidayData) => {
    try {
      const response = await apiClient.patch(`events/holidays/${holidayId}/`, holidayData);
      return response.data;
    } catch (error) {
      handleError(error);
      throw error;
    }
  },

  deleteHoliday: async (holidayId) => {
    try {
      await apiClient.delete(`events/holidays/${holidayId}/`);
    } catch (error) {
      handleError(error);
      throw error;
    }
  },
};
