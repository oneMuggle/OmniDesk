import meetingRoomApi from './meetingRoomApi';
import apiClient from '../../../shared/api/apiClient';

jest.mock('../../../shared/api/apiClient', () => ({
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  patch: jest.fn(),
  delete: jest.fn(),
}));

describe('meetingRoomApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Meeting Rooms', () => {
    it('should get all meeting rooms', async () => {
      apiClient.get.mockResolvedValue({ data: { results: [{ id: 1, name: 'Room A' }] } });

      const result = await meetingRoomApi.getMeetingRooms();

      expect(apiClient.get).toHaveBeenCalledWith('meeting-rooms/meeting-rooms/');
      expect(result.data.results).toHaveLength(1);
    });

    it('should get a single meeting room', async () => {
      apiClient.get.mockResolvedValue({ data: { id: 1, name: 'Room A' } });

      await meetingRoomApi.getMeetingRoom(1);

      expect(apiClient.get).toHaveBeenCalledWith('meeting-rooms/meeting-rooms/1/');
    });

    it('should create a meeting room', async () => {
      apiClient.post.mockResolvedValue({ data: { id: 1, name: 'New Room' } });

      await meetingRoomApi.createMeetingRoom({ name: 'New Room' });

      expect(apiClient.post).toHaveBeenCalledWith('meeting-rooms/meeting-rooms/', { name: 'New Room' });
    });

    it('should update a meeting room', async () => {
      apiClient.put.mockResolvedValue({ data: { id: 1, name: 'Updated' } });

      await meetingRoomApi.updateMeetingRoom(1, { name: 'Updated' });

      expect(apiClient.put).toHaveBeenCalledWith('meeting-rooms/meeting-rooms/1/', { name: 'Updated' });
    });

    it('should partial update a meeting room', async () => {
      apiClient.patch.mockResolvedValue({ data: { id: 1, name: 'Patched' } });

      await meetingRoomApi.partialUpdateMeetingRoom(1, { name: 'Patched' });

      expect(apiClient.patch).toHaveBeenCalledWith('meeting-rooms/meeting-rooms/1/', { name: 'Patched' });
    });

    it('should delete a meeting room', async () => {
      apiClient.delete.mockResolvedValue({});

      await meetingRoomApi.deleteMeetingRoom(1);

      expect(apiClient.delete).toHaveBeenCalledWith('meeting-rooms/meeting-rooms/1/');
    });
  });

  describe('Meeting Room Bookings', () => {
    it('should get bookings with params', async () => {
      apiClient.get.mockResolvedValue({ data: { results: [{ id: 1 }] } });

      await meetingRoomApi.getMeetingRoomBookings({ room_id: 1 });

      expect(apiClient.get).toHaveBeenCalledWith('meeting-rooms/meeting-room-bookings/', { params: { room_id: 1 } });
    });

    it('should create a booking', async () => {
      apiClient.post.mockResolvedValue({ data: { id: 1, room_id: 1 } });

      await meetingRoomApi.createMeetingRoomBooking({ room_id: 1, date: '2024-01-01' });

      expect(apiClient.post).toHaveBeenCalledWith('meeting-rooms/meeting-room-bookings/', { room_id: 1, date: '2024-01-01' });
    });

    it('should update a booking', async () => {
      apiClient.put.mockResolvedValue({ data: { id: 1 } });

      await meetingRoomApi.updateMeetingRoomBooking(1, { date: '2024-01-02' });

      expect(apiClient.put).toHaveBeenCalledWith('meeting-rooms/meeting-room-bookings/1/', { date: '2024-01-02' });
    });

    it('should delete a booking', async () => {
      apiClient.delete.mockResolvedValue({});

      await meetingRoomApi.deleteMeetingRoomBooking(1);

      expect(apiClient.delete).toHaveBeenCalledWith('meeting-rooms/meeting-room-bookings/1/');
    });
  });

  describe('Meeting Room Maintenance', () => {
    it('should get maintenance records', async () => {
      apiClient.get.mockResolvedValue({ data: { results: [] } });

      await meetingRoomApi.getMeetingRoomMaintenances({ room_id: 1 });

      expect(apiClient.get).toHaveBeenCalledWith('meeting-rooms/meeting-room-maintenance/', { params: { room_id: 1 } });
    });

    it('should create a maintenance record', async () => {
      apiClient.post.mockResolvedValue({ data: { id: 1 } });

      await meetingRoomApi.createMeetingRoomMaintenance({ room_id: 1, type: 'clean' });

      expect(apiClient.post).toHaveBeenCalledWith('meeting-rooms/meeting-room-maintenance/', { room_id: 1, type: 'clean' });
    });

    it('should delete a maintenance record', async () => {
      apiClient.delete.mockResolvedValue({});

      await meetingRoomApi.deleteMeetingRoomMaintenance(1);

      expect(apiClient.delete).toHaveBeenCalledWith('meeting-rooms/meeting-room-maintenance/1/');
    });
  });

  describe('Meeting Room Stats', () => {
    it('should get stats with params', async () => {
      apiClient.get.mockResolvedValue({ data: { total: 10, occupied: 5 } });

      const result = await meetingRoomApi.getMeetingRoomStats({ month: '2024-01' });

      expect(apiClient.get).toHaveBeenCalledWith('meeting-rooms/meeting-room-stats/', { params: { month: '2024-01' } });
      expect(result.data.total).toBe(10);
    });
  });
});
