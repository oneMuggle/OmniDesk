import React from 'react';
import { render, screen, fireEvent, waitFor, within, act } from '@testing-library/react';
import PropTypes from 'prop-types';
import '@testing-library/jest-dom';
import dayjs from 'dayjs';
import { Form } from 'antd';
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
    const roomAElements = await screen.findAllByText('Room A');
    expect(roomAElements.length).toBeGreaterThan(0);
    await screen.findByText('Projector issue');
    await screen.findByText('总预约数量');
  });

  describe('Meeting Room CRUD', () => {
    test('adds a new meeting room', async () => {
      renderWithAuth(<MeetingRoomManagementPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

      const addRoomButton = await screen.findByRole('button', { name: /添加会议室/i });
      fireEvent.click(addRoomButton);
      
      const dialog = await screen.findByRole('dialog', { name: /添加会议室/i });
      
      const nameInput = await within(dialog).findByLabelText('名称');
      fireEvent.change(nameInput, { target: { value: 'Room C' } });
      
      const okButton = await within(dialog).findByRole('button', { name: 'OK' });
      fireEvent.click(okButton);

      await waitFor(() => {
        expect(meetingRoomApi.createMeetingRoom).toHaveBeenCalledWith(expect.objectContaining({ name: 'Room C' }));
      });
    });

    test('edits an existing meeting room', async () => {
      renderWithAuth(<MeetingRoomManagementPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

      const editButton = await screen.findByLabelText('edit-room-1');
      fireEvent.click(editButton);

      const dialog = await screen.findByRole('dialog', { name: /编辑会议室/i });
      
      const nameInput = await within(dialog).findByLabelText('名称');
      expect(nameInput).toHaveValue('Room A');
      fireEvent.change(nameInput, { target: { value: 'Room A Updated' } });
      
      const okButton = await within(dialog).findByRole('button', { name: 'OK' });
      fireEvent.click(okButton);

      await waitFor(() => {
        expect(meetingRoomApi.updateMeetingRoom).toHaveBeenCalledWith(1, expect.objectContaining({ name: 'Room A Updated' }));
      });
    });

    test('deletes an existing meeting room', async () => {
      renderWithAuth(<MeetingRoomManagementPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

      const deleteButton = await screen.findByLabelText('delete-room-1');
      fireEvent.click(deleteButton);

      const confirmButton = await screen.findByRole('button', { name: /ok/i });
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(meetingRoomApi.deleteMeetingRoom).toHaveBeenCalledWith(1);
      });
    });
  });

  describe('Maintenance CRUD', () => {
    test('adds a new maintenance record', async () => {
        const TestWrapper = ({ formRef }) => {
            const [form] = Form.useForm();
            React.useImperativeHandle(formRef, () => form);
            return <MeetingRoomManagementPage maintenanceForm={form} />;
        };

        TestWrapper.propTypes = {
            formRef: PropTypes.object,
        };

        const maintenanceFormRef = React.createRef();
        renderWithAuth(<TestWrapper formRef={maintenanceFormRef} />, { providerProps: { user: mockUser, isAuthenticated: true } });

        const addMaintenanceButton = await screen.findByRole('button', { name: /添加维护记录/i });
        fireEvent.click(addMaintenanceButton);

        const dialog = await screen.findByRole('dialog', { name: /添加维护记录/i });

        await act(async () => {
            maintenanceFormRef.current.setFieldsValue({
                meeting_room: 1,
                timeRange: [dayjs('2025-12-20T10:00:00Z'), dayjs('2025-12-20T11:00:00Z')],
                reason: 'Cleaning',
            });
        });

        const okButton = within(dialog).getByRole('button', { name: 'OK' });
        fireEvent.click(okButton);

        await waitFor(() => {
            const expectedStartTime = '2025-12-20T10:00:00.000Z';
            const expectedEndTime = '2025-12-20T11:00:00.000Z';
            expect(meetingRoomApi.createMeetingRoomMaintenance).toHaveBeenCalledWith(expect.objectContaining({
                meeting_room: 1,
                reason: 'Cleaning',
                start_time: expectedStartTime,
                end_time: expectedEndTime,
            }));
        });
    });
  });

  describe('Stats Filtering', () => {
    test('refreshes stats when filter changes', async () => {
      renderWithAuth(<MeetingRoomManagementPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

      await screen.findByText('总预约数量');
      
      // Change the filter to trigger a refresh, which aligns with the test name
      const roomSelect = screen.getByText('选择会议室');
      fireEvent.mouseDown(roomSelect);
      const roomAOption = await screen.findByRole('option', { name: 'Room A' });
      fireEvent.click(roomAOption);

      const refreshButton = await screen.findByRole('button', { name: /刷新统计/i });
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(meetingRoomApi.getMeetingRoomStats).toHaveBeenCalledTimes(2); // Initial fetch + fetch on filter change
      });
    });
  });
});