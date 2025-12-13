import apiClient from './apiClient';

const userManagementApi = {
    getAllUsers: () => apiClient.get('/users/dashboard/'),
    updateUserRole: (userId, role) => apiClient.patch(`/users/dashboard/${userId}/`, { role }),
    associateUserWithPersonnel: (userId, personnelId) => apiClient.patch(`/users/dashboard/${userId}/`, { personnel_id: personnelId }),
    createUser: (userData) => apiClient.post('/users/dashboard/', userData),
    updateUser: (userId, userData) => apiClient.patch(`/users/dashboard/${userId}/`, userData),
    updateUserGroups: (userId, groups) => apiClient.patch(`/users/dashboard/${userId}/`, { groups }),
    getGroups: () => apiClient.get('/permissions/groups/'),
    getGroupedPermissions: () => apiClient.get('/permissions/permissions/grouped/'),
    getGroupPermissions: (groupId) => apiClient.get(`/permissions/groups/${groupId}/permissions/`),
    updateGroupPermissions: (groupId, permissions) => apiClient.put(`/permissions/groups/${groupId}/permissions/`, { permissions }),
};

export default userManagementApi;