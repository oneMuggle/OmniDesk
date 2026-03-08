import React from 'react';
import { render, screen, waitFor, within, act, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PropTypes from 'prop-types';
import '@testing-library/jest-dom';
import dayjs from 'dayjs';
import { Form } from 'antd';
import MeetingRoomManagementPage from './MeetingRoomManagementPage';
import meetingRoomApi from '../api/meetingRoomApi';
import { AuthContext } from '../../auth/context/AuthContext';

jest.mock('../api/meetingRoomApi');

const mockedMeetingRoomApi = jest.mocked(meetingRoomApi);

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
    mockedMeetingRoomApi.getMeetingRooms.mockResolvedValue(mockMeetingRooms);
    mockedMeetingRoomApi.getMeetingRoomMaintenances.mockResolvedValue(mockMaintenances);
    mockedMeetingRoomApi.getMeetingRoomStats.mockResolvedValue(mockStats);
    mockedMeetingRoomApi.createMeetingRoom.mockResolvedValue({ success: true });
    mockedMeetingRoomApi.updateMeetingRoom.mockResolvedValue({ success: true });
    mockedMeetingRoomApi.deleteMeetingRoom.mockResolvedValue({ success: true });
    mockedMeetingRoomApi.createMeetingRoomMaintenance.mockResolvedValue({ success: true });
    mockedMeetingRoomApi.updateMeetingRoomMaintenance.mockResolvedValue({ success: true });
    mockedMeetingRoomApi.deleteMeetingRoomMaintenance.mockResolvedValue({ success: true });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should render the component and fetch initial data', async () => {
    renderWithAuth(<MeetingRoomManagementPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

    expect(screen.getByRole('heading', { name: /会议室管理/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(mockedMeetingRoomApi.getMeetingRooms).toHaveBeenCalledTimes(1);
    });
    expect(mockedMeetingRoomApi.getMeetingRoomMaintenances).toHaveBeenCalledTimes(1);
    expect(mockedMeetingRoomApi.getMeetingRoomStats).toHaveBeenCalledTimes(1);

    // Check if data is rendered
    const roomAElements = await screen.findAllByText('Room A');
    expect(roomAElements.length).toBeGreaterThan(0);
    expect(await screen.findByText('Projector issue')).toBeInTheDocument();
    expect(await screen.findByText('总预约数量')).toBeInTheDocument();
  });

  describe('Meeting Room CRUD', () => {
    it('should allow adding a new meeting room', async () => {
      const user = userEvent.setup();
      renderWithAuth(<MeetingRoomManagementPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

      const addRoomButton = await screen.findByRole('button', { name: /添加会议室/i });
      await user.click(addRoomButton);
      
      const dialog = await screen.findByRole('dialog', { name: /添加会议室/i });
      
      const nameInput = within(dialog).getByLabelText('名称');
      await user.type(nameInput, 'Room C');
      
      const okButton = within(dialog).getByRole('button', { name: 'OK' });
      await user.click(okButton);

      await waitFor(() => {
        expect(mockedMeetingRoomApi.createMeetingRoom).toHaveBeenCalledWith(expect.objectContaining({ name: 'Room C' }));
      });
    });

    it('should allow editing an existing meeting room', async () => {
      const user = userEvent.setup();
      renderWithAuth(<MeetingRoomManagementPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

      const editButton = await screen.findByLabelText('edit-room-1');
      await user.click(editButton);

      const dialog = await screen.findByRole('dialog', { name: /编辑会议室/i });
      
      const nameInput = within(dialog).getByLabelText('名称');
      expect(nameInput).toHaveValue('Room A');
      await user.clear(nameInput);
      await user.type(nameInput, 'Room A Updated');
      
      const okButton = within(dialog).getByRole('button', { name: 'OK' });
      await user.click(okButton);

      await waitFor(() => {
        expect(mockedMeetingRoomApi.updateMeetingRoom).toHaveBeenCalledWith(1, expect.objectContaining({ name: 'Room A Updated' }));
      });
    });

    it('should allow deleting a meeting room', async () => {
      const user = userEvent.setup();
      renderWithAuth(<MeetingRoomManagementPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

      const deleteButton = await screen.findByLabelText('delete-room-1');
      await user.click(deleteButton);

      const confirmButton = await screen.findByRole('button', { name: /ok/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(mockedMeetingRoomApi.deleteMeetingRoom).toHaveBeenCalledWith(1);
      });
    });
  });

  describe('Maintenance CRUD', () => {
    it('should allow adding a new maintenance record', async () => {
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
            expect(mockedMeetingRoomApi.createMeetingRoomMaintenance).toHaveBeenCalledWith(expect.objectContaining({
                meeting_room: 1,
                reason: 'Cleaning',
                start_time: expectedStartTime,
                end_time: expectedEndTime,
            }));
        });
    });
  });

  describe('Stats Filtering', () => {
    it('should refetch stats when filters are applied', async () => {
      const user = userEvent.setup();
      renderWithAuth(<MeetingRoomManagementPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

      await screen.findByText('总预约数量');
      expect(mockedMeetingRoomApi.getMeetingRoomStats).toHaveBeenCalledTimes(1);
      
      const roomSelect = screen.getByRole('combobox');
      await user.click(roomSelect);
      const roomAOption = await screen.findByRole('option', { name: 'Room A' });
      await user.click(roomAOption);

      const refreshButton = await screen.findByRole('button', { name: /刷新统计/i });
      await user.click(refreshButton);

      await waitFor(() => {
        expect(mockedMeetingRoomApi.getMeetingRoomStats).toHaveBeenCalledTimes(2);
      });
    });
  });
});