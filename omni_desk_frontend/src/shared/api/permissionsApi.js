import apiClient from './apiClient';

// Helper to get CSRF token from cookies
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

// Helper to handle API requests
const request = async (url, options = {}) => {
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

export const permissionsApi = {
  /**
   * Fetches all user groups.
   * GET /permissions/groups/
   */
  getGroups: () => apiClient.get('/permissions/groups/'),

  /**
   * Creates a new user group.
   * POST /permissions/groups/
   * @param {object} groupData The data for the new group (e.g., { name: 'New Group' }).
   */
  createGroup: (groupData) => {
    return request('/permissions/groups/', {
      method: 'POST',
      body: JSON.stringify(groupData),
    });
  },

  /**
   * Updates an existing user group.
   * PUT /permissions/groups/{id}/
   * @param {number} groupId The ID of the group to update.
   * @param {object} groupData The updated data for the group (e.g., { name: 'Updated Group' }).
   */
  updateGroup: (groupId, groupData) => {
    return request(`/permissions/groups/${groupId}/`, {
      method: 'PUT',
      body: JSON.stringify(groupData),
    });
  },

  /**
   * Deletes a user group.
   * DELETE /permissions/groups/{id}/
   * @param {number} groupId The ID of the group to delete.
   */
  deleteGroup: (groupId) => {
    return request(`/permissions/groups/${groupId}/`, {
      method: 'DELETE',
    });
  },

  /**
   * Fetches the entire page permission tree.
   * GET /permissions/pages/
   */
  getPageTree: () => {
    return request('/permissions/pages/');
  },

  /**
   * Fetches permissions for a specific group.
   * GET /permissions/groups/{id}/permissions/
   * @param {number} groupId The ID of the group.
   */
  getGroupPermissions: (groupId) => {
    return request(`/permissions/groups/${groupId}/permissions/`);
  },

  /**
   * Updates permissions for a specific group.
   * PUT /permissions/groups/{id}/permissions/
   * @param {number} groupId The ID of the group.
   * @param {number[]} permissionIds An array of permission IDs.
   */
  updateGroupPermissions: (groupId, permissionIds) => {
    return request(`/permissions/groups/${groupId}/permissions/`, {
      method: 'PUT',
      body: JSON.stringify({ permissions: permissionIds }),
    });
  },

  /**
   * Fetches permissions for the current user.
   * GET /permissions/users/me/permissions/
   */
  getMyPermissions: () => {
    return request('/permissions/users/me/permissions/');
  },
};