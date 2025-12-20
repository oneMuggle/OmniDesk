import apiClient from '../../../shared/api/apiClient';

const meetingRoomApi = {
    getMeetingRooms: () => apiClient.get('/meeting-rooms/meeting-rooms/'),
    getMeetingRoom: (id) => apiClient.get(`/meeting-rooms/meeting-rooms/${id}/`),
    createMeetingRoom: (data) => apiClient.post('/meeting-rooms/meeting-rooms/', data),
    updateMeetingRoom: (id, data) => apiClient.put(`/meeting-rooms/meeting-rooms/${id}/`, data),
    partialUpdateMeetingRoom: (id, data) => apiClient.patch(`/meeting-rooms/meeting-rooms/${id}/`, data),
    deleteMeetingRoom: (id) => apiClient.delete(`/meeting-rooms/meeting-rooms/${id}/`),

    getMeetingRoomBookings: (params) => apiClient.get('/meeting-rooms/meeting-room-bookings/', { params }),
    getMeetingRoomBooking: (id) => apiClient.get(`/meeting-rooms/meeting-room-bookings/${id}/`),
    createMeetingRoomBooking: (data) => apiClient.post('/meeting-rooms/meeting-room-bookings/', data),
    updateMeetingRoomBooking: (id, data) => apiClient.put(`/meeting-rooms/meeting-room-bookings/${id}/`, data),
    partialUpdateMeetingRoomBooking: (id, data) => apiClient.patch(`/meeting-rooms/meeting-room-bookings/${id}/`, data),
    deleteMeetingRoomBooking: (id) => apiClient.delete(`/meeting-rooms/meeting-room-bookings/${id}/`),

    getMeetingRoomMaintenances: (params) => apiClient.get('/meeting-rooms/meeting-room-maintenance/', { params }),
    getMeetingRoomMaintenance: (id) => apiClient.get(`/meeting-rooms/meeting-room-maintenance/${id}/`),
    createMeetingRoomMaintenance: (data) => apiClient.post('/meeting-rooms/meeting-room-maintenance/', data),
    updateMeetingRoomMaintenance: (id, data) => apiClient.put(`/meeting-rooms/meeting-room-maintenance/${id}/`, data),
    partialUpdateMeetingRoomMaintenance: (id, data) => apiClient.patch(`/meeting-rooms/meeting-room-maintenance/${id}/`, data),
    deleteMeetingRoomMaintenance: (id) => apiClient.delete(`/meeting-rooms/meeting-room-maintenance/${id}/`),

    getMeetingRoomStats: (params) => apiClient.get('/meeting-rooms/meeting-room-stats/', { params }),
};

export default meetingRoomApi;