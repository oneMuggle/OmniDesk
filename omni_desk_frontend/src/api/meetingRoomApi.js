import apiClient from './apiClient';

const meetingRoomApi = {
    getMeetingRooms: () => apiClient.get('/meeting-rooms/'),
    getMeetingRoom: (id) => apiClient.get(`/meeting-rooms/${id}/`),
    createMeetingRoom: (data) => apiClient.post('/meeting-rooms/', data),
    updateMeetingRoom: (id, data) => apiClient.put(`/meeting-rooms/${id}/`, data),
    partialUpdateMeetingRoom: (id, data) => apiClient.patch(`/meeting-rooms/${id}/`, data),
    deleteMeetingRoom: (id) => apiClient.delete(`/meeting-rooms/${id}/`),

    getMeetingRoomBookings: (params) => apiClient.get('/meeting-room-bookings/', { params }),
    getMeetingRoomBooking: (id) => apiClient.get(`/meeting-room-bookings/${id}/`),
    createMeetingRoomBooking: (data) => apiClient.post('/meeting-room-bookings/', data),
    updateMeetingRoomBooking: (id, data) => apiClient.put(`/meeting-room-bookings/${id}/`, data),
    partialUpdateMeetingRoomBooking: (id, data) => apiClient.patch(`/meeting-room-bookings/${id}/`, data),
    deleteMeetingRoomBooking: (id) => apiClient.delete(`/meeting-room-bookings/${id}/`),

    getMeetingRoomMaintenances: (params) => apiClient.get('/meeting-room-maintenances/', { params }),
    getMeetingRoomMaintenance: (id) => apiClient.get(`/meeting-room-maintenances/${id}/`),
    createMeetingRoomMaintenance: (data) => apiClient.post('/meeting-room-maintenances/', data),
    updateMeetingRoomMaintenance: (id, data) => apiClient.put(`/meeting-room-maintenances/${id}/`, data),
    partialUpdateMeetingRoomMaintenance: (id, data) => apiClient.patch(`/meeting-room-maintenances/${id}/`, data),
    deleteMeetingRoomMaintenance: (id) => apiClient.delete(`/meeting-room-maintenances/${id}/`),

    getMeetingRoomStats: (params) => apiClient.get('/meeting-room-stats/', { params }),
};

export default meetingRoomApi;