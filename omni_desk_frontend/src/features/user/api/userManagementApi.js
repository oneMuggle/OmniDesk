import apiClient from '../../../shared/api/apiClient';

const userManagementApi = {
    getAllUsers: () => apiClient.get('users/control-panel/'),
    associateUserWithPersonnel: (userId, personnelId) => apiClient.patch(`users/control-panel/${userId}/`, { personnel_id: personnelId }),
    createUser: (userData) => apiClient.post('users/control-panel/', userData),
    updateUser: (userId, userData) => apiClient.patch(`users/control-panel/${userId}/`, userData),
    updateUserGroups: (userId, groups) => apiClient.patch(`users/control-panel/${userId}/`, { groups }),
    deleteUser: (userId) => apiClient.delete(`users/control-panel/${userId}/`),
    getGroups: () => apiClient.get('permissions/groups/'),
    getGroupedPermissions: () => apiClient.get('permissions/permissions/grouped/'),
    getGroupPermissions: (groupId) => apiClient.get(`permissions/groups/${groupId}/permissions/`),
    updateGroupPermissions: (groupId, permissions) => apiClient.put(`permissions/groups/${groupId}/permissions/`, { permissions }),
};

export default userManagementApi;