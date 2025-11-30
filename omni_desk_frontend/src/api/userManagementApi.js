import apiClient from './apiClient';

// Helper to get CSRF token from cookies, copied from permissionsApi.js
const getCookie = (name) => {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
};

// Helper to handle API requests, copied from permissionsApi.js
const customRequest = async (url, options = {}) => {
  const headers = {
    'Content-Type': 'application/json',
    'X-CSRFToken': getCookie('csrftoken'),
    ...options.headers,
  };

  const response = await fetch(`/api${url}`, { ...options, headers });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.detail || error.message || 'API request failed');
  }

  if (response.status === 204) {
    return null; // No content
  }

  return response.json();
};


const userManagementApi = {
    getAllUsers: () => apiClient.get('/users/admin/'),
    updateUserRole: (userId, role) => apiClient.patch(`/users/admin/${userId}/`, { role }),
    associateUserWithPersonnel: (userId, personnelId) => apiClient.patch(`/users/admin/${userId}/`, { personnel_id: personnelId }),
    createUser: (userData) => apiClient.post('/users/admin/', userData),
    updateUser: (userId, userData) => apiClient.patch(`/users/admin/${userId}/`, userData),
    // Rewrite updateUserGroups to use the proven custom fetch method
    updateUserGroups: (userId, groups) => {
        return customRequest(`/users/admin/${userId}/`, {
            method: 'PATCH',
            body: JSON.stringify({ groups }),
        });
    },
};

export default userManagementApi;