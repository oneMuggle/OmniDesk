import apiClient from './apiClient';

const userManagementApi = {
    getAllUsers: () => apiClient.get('/users/admin/'),
    updateUserRole: (userId, role) => apiClient.patch(`/users/admin/${userId}/`, { role }),
    associateUserWithPersonnel: (userId, personnelId) => apiClient.patch(`/users/admin/${userId}/`, { personnel_id: personnelId }),
    createUser: (userData) => apiClient.post('/users/admin/', userData),
    updateUser: (userId, userData) => apiClient.patch(`/users/admin/${userId}/`, userData),
    updateUserGroups: (userId, groups) => apiClient.patch(`/users/admin/${userId}/`, { groups }),
};

export default userManagementApi;