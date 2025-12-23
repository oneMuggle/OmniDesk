import apiClient from '../../../shared/api/apiClient';

const userManagementApi = {
    getAllUsers: () => apiClient.get('/api/users/control-panel/'),
    associateUserWithPersonnel: (userId, personnelId) => apiClient.patch(`/api/users/control-panel/${userId}/`, { personnel_id: personnelId }),
    createUser: (userData) => apiClient.post('/api/users/control-panel/', userData),
    updateUser: (userId, userData) => apiClient.patch(`/api/users/control-panel/${userId}/`, userData),
    updateUserGroups: (userId, groups) => apiClient.patch(`/api/users/control-panel/${userId}/`, { groups }),
    getGroups: () => apiClient.get('/api/permissions/groups/'),
    getGroupedPermissions: () => apiClient.get('/api/permissions/permissions/grouped/'),
    getGroupPermissions: (groupId) => apiClient.get(`/api/permissions/groups/${groupId}/permissions/`),
    updateGroupPermissions: (groupId, permissions) => apiClient.put(`/api/permissions/groups/${groupId}/permissions/`, { permissions }),
};

export default userManagementApi;