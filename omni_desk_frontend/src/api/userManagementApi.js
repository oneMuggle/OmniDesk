import apiClient from './apiClient';

const userManagementApi = {
    getAllUsers: () => apiClient.get('/users/admin/'),
    updateUserRole: (userId, role) => apiClient.patch(`/users/admin/${userId}/`, { role }),
};

export default userManagementApi;