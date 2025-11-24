import apiClient from './apiClient';

const meetingRoomApi = {
    getMeetingRooms: () => apiClient.get('/api/meeting-rooms/'),
    getMeetingRoom: (id) => apiClient.get(`/api/meeting-rooms/${id}/`),
    createMeetingRoom: (data) => apiClient.post('/api/meeting-rooms/', data),
    updateMeetingRoom: (id, data) => apiClient.put(`/api/meeting-rooms/${id}/`, data),
    partialUpdateMeetingRoom: (id, data) => apiClient.patch(`/api/meeting-rooms/${id}/`, data),
    deleteMeetingRoom: (id) => apiClient.delete(`/api/meeting-rooms/${id}/`),

    getMeetingRoomBookings: (params) => apiClient.get('/api/meeting-room-bookings/', { params }),
    getMeetingRoomBooking: (id) => apiClient.get(`/api/meeting-room-bookings/${id}/`),
    createMeetingRoomBooking: (data) => apiClient.post('/api/meeting-room-bookings/', data),
    updateMeetingRoomBooking: (id, data) => apiClient.put(`/api/meeting-room-bookings/${id}/`, data),
    partialUpdateMeetingRoomBooking: (id, data) => apiClient.patch(`/api/meeting-room-bookings/${id}/`, data),
    deleteMeetingRoomBooking: (id) => apiClient.delete(`/api/meeting-room-bookings/${id}/`),

    getMeetingRoomMaintenances: (params) => apiClient.get('/api/meeting-room-maintenances/', { params }),
    getMeetingRoomMaintenance: (id) => apiClient.get(`/api/meeting-room-maintenances/${id}/`),
    createMeetingRoomMaintenance: (data) => apiClient.post('/api/meeting-room-maintenances/', data),
    updateMeetingRoomMaintenance: (id, data) => apiClient.put(`/api/meeting-room-maintenances/${id}/`, data),
    partialUpdateMeetingRoomMaintenance: (id, data) => apiClient.patch(`/api/meeting-room-maintenances/${id}/`, data),
    deleteMeetingRoomMaintenance: (id) => apiClient.delete(`/api/meeting-room-maintenances/${id}/`),

    getMeetingRoomStats: (params) => apiClient.get('/api/meeting-room-stats/', { params }),
};

export default meetingRoomApi;