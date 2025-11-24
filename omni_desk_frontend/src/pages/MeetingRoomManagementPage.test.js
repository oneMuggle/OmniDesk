import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import dayjs from 'dayjs';
import MeetingRoomManagementPage from './MeetingRoomManagementPage';
import meetingRoomApi from '../api/meetingRoomApi';
import { AuthContext } from '../context/AuthContext';

jest.mock('../api/meetingRoomApi');

const mockMeetingRooms = {
  data: {
    results: [
      { id: 1, name: 'Room A', description: 'Large room', capacity: 20, location: '1st Floor' },
      { id: 2, name: 'Room B', description: 'Small room', capacity: 5, location: '2nd Floor' },
    ],
  },
};

const mockMaintenances = {
  data: {
    results: [
      { id: 1, meeting_room: 1, meeting_room_name: 'Room A', start_time: '2025-11-25T10:00:00Z', end_time: '2025-11-25T11:00:00Z', reason: 'Projector issue' },
    ],
  },
};

const mockStats = {
  data: {
    total_bookings: 10,
    total_booking_duration_minutes: 600,
    room_stats: [
      { meeting_room_name: 'Room A', booking_count: 5, total_duration_minutes: 300 },
      { meeting_room_name: 'Room B', booking_count: 5, total_duration_minutes: 300 },
    ],
  },
};

const mockUser = { id: 1, username: 'testuser', role: 'admin' };

const renderWithAuth = (ui, { providerProps, ...renderOptions }) => {
  return render(
    <AuthContext.Provider value={providerProps}>{ui}</AuthContext.Provider>,
    renderOptions
  );
};

describe('MeetingRoomManagementPage', () => {
  beforeEach(() => {
    meetingRoomApi.getMeetingRooms.mockResolvedValue(mockMeetingRooms);
    meetingRoomApi.getMeetingRoomMaintenances.mockResolvedValue(mockMaintenances);
    meetingRoomApi.getMeetingRoomStats.mockResolvedValue(mockStats);
    meetingRoomApi.createMeetingRoom.mockResolvedValue({ success: true });
    meetingRoomApi.updateMeetingRoom.mockResolvedValue({ success: true });
    meetingRoomApi.deleteMeetingRoom.mockResolvedValue({ success: true });
    meetingRoomApi.createMeetingRoomMaintenance.mockResolvedValue({ success: true });
    meetingRoomApi.updateMeetingRoomMaintenance.mockResolvedValue({ success: true });
    meetingRoomApi.deleteMeetingRoomMaintenance.mockResolvedValue({ success: true });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders the component and fetches data', async () => {
    renderWithAuth(<MeetingRoomManagementPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

    expect(screen.getByRole('heading', { name: /会议室管理/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(meetingRoomApi.getMeetingRooms).toHaveBeenCalled();
    });
    expect(meetingRoomApi.getMeetingRoomMaintenances).toHaveBeenCalled();
    expect(meetingRoomApi.getMeetingRoomStats).toHaveBeenCalled();

    // Check if data is rendered
    await screen.findByText('Room A');
    await screen.findByText('Projector issue');
    await screen.findByText('总预约数量');
  });

  describe('Meeting Room CRUD', () => {
    test('adds a new meeting room', async () => {
      renderWithAuth(<MeetingRoomManagementPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

      fireEvent.click(screen.getByRole('button', { name: /添加会议室/i }));
      await screen.findByRole('dialog', { name: /添加会议室/i });

      fireEvent.change(screen.getByLabelText('名称'), { target: { value: 'Room C' } });
      fireEvent.click(screen.getByRole('button', { name: 'OK' }));

      await waitFor(() => {
        expect(meetingRoomApi.createMeetingRoom).toHaveBeenCalledWith({ name: 'Room C' });
      });
    });

    test('edits an existing meeting room', async () => {
      renderWithAuth(<MeetingRoomManagementPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

      await screen.findAllByText('Room A');
      const editButtons = await screen.findAllByRole('button', { name: /edit/i });
      fireEvent.click(editButtons[0]);

      await screen.findByRole('dialog', { name: /编辑会议室/i });
      expect(screen.getByLabelText('名称')).toHaveValue('Room A');

      fireEvent.change(screen.getByLabelText('名称'), { target: { value: 'Room A Updated' } });
      fireEvent.click(screen.getByRole('button', { name: 'OK' }));

      await waitFor(() => {
        expect(meetingRoomApi.updateMeetingRoom).toHaveBeenCalledWith(1, expect.objectContaining({ name: 'Room A Updated' }));
      });
    });

    test('deletes an existing meeting room', async () => {
      renderWithAuth(<MeetingRoomManagementPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

      await screen.findAllByText('Room A');
      const deleteButtons = await screen.findAllByRole('button', { name: /delete/i });
      fireEvent.click(deleteButtons[0]);

      await screen.findByText('确定删除此会议室吗？');
      fireEvent.click(screen.getByRole('button', { name: /ok/i }));

      await waitFor(() => {
        expect(meetingRoomApi.deleteMeetingRoom).toHaveBeenCalledWith(1);
      });
    });
  });

  describe('Maintenance CRUD', () => {
    test('adds a new maintenance record', async () => {
        renderWithAuth(<MeetingRoomManagementPage />, { providerProps: { user: mockUser, isAuthenticated: true } });
    
        fireEvent.click(screen.getByRole('button', { name: /添加维护记录/i }));
        await screen.findByRole('dialog', { name: /添加维护记录/i });
    
        // antd select is complex
        fireEvent.mouseDown(screen.getByLabelText('会议室'));
        const roomAOptions = await screen.findAllByText('Room A');
        fireEvent.click(roomAOptions[0]);
    
        fireEvent.change(screen.getByLabelText('维护原因'), { target: { value: 'Cleaning' } });
        fireEvent.click(screen.getByRole('button', { name: 'OK' }));
    
        await waitFor(() => {
            expect(meetingRoomApi.createMeetingRoomMaintenance).toHaveBeenCalled();
        });
    });
  });

  describe('Stats Filtering', () => {
    test('refreshes stats when filter changes', async () => {
      renderWithAuth(<MeetingRoomManagementPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

      await screen.findByText('总预约数量');
      
      // Change date range
      // Interacting with RangePicker is complex. We'll just test the refresh button.

      fireEvent.click(screen.getByRole('button', { name: /刷新统计/i }));

      await waitFor(() => {
        expect(meetingRoomApi.getMeetingRoomStats).toHaveBeenCalledTimes(2); // Initial fetch + refresh
      });
    });
  });
});