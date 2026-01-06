import apiClient from './apiClient';

const complianceApi = {
  getUnreadCount: () => {
    return apiClient.get('compliance/unread-count/');
  },
};

export default complianceApi;