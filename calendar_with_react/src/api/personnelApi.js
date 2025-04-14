import { apiClient } from '../context/AuthContext';
import { handleError } from './responseHandler';

export const personnelApi = {
  getPersonnel: async () => {
    try {
      const response = await apiClient.get('/api/events/personnel/');
      return response.data.map(person => ({
        id: person.id,
        name: person.name,
        phone: person.phone,
        email: person.email,
        role: person.role,
        department: person.department
      }));
    } catch (error) {
      handleError(error);
      throw error;
    }
  }
};
