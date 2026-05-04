import apiClient from '../../../shared/api/apiClient';

const BASE_URL = 'notifications';

const notificationApi = {
  getList: (params) => apiClient.get(BASE_URL, { params }),
  getById: (id) => apiClient.get(`${BASE_URL}/${id}/`),
  markRead: (id) => apiClient.patch(`${BASE_URL}/${id}/mark_read/`),
  markAllRead: () => apiClient.post(`${BASE_URL}/mark_all_read/`),
  getUnreadCount: () => apiClient.get(`${BASE_URL}/unread_count/`),
};

export default notificationApi;
