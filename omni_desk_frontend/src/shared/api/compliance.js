import apiClient from './apiClient';

const complianceApi = {
  getUnreadCount: () => {
    return apiClient.get('/api/compliance/unread-count/');
  },
};

export default complianceApi;