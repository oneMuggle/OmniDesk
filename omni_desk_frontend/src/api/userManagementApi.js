import apiClient from './apiClient';

const userManagementApi = {
    getAllUsers: () => apiClient.get('/users/admin/'),
    updateUserRole: (userId, role) => apiClient.patch(`/users/admin/${userId}/`, { role }),
    associateUserWithPersonnel: (userId, personnelId) => apiClient.patch(`/users/admin/${userId}/`, { personnel_id: personnelId }),
};

export default userManagementApi;