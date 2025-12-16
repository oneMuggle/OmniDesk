import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import MeetingRoomBookingPage from './MeetingRoomBookingPage';
import meetingRoomApi from '../api/meetingRoomApi';
import { AuthContext } from '../context/AuthContext';
import { MemoryRouter } from 'react-router-dom';
import dayjs from 'dayjs';

jest.mock('../api/meetingRoomApi');

const mockMeetingRooms = {
  data: {
    results: [
      { id: 1, name: 'Room A' },
      { id: 2, name: 'Room B' },
    ],
  },
};

const mockBookings = {
  data: {
    results: [
      { id: 1, title: 'Team Meeting', start_time: '2025-12-16T10:00:00Z', end_time: '2025-12-16T11:00:00Z', meeting_room: 1, meeting_room_name: 'Room A', user: { id: 1, username: 'testuser', real_name: 'Test User', phone_numbers: [{ number: '1234567890' }] } },
      { id: 2, title: 'Project Sync', start_time: '2025-12-17T14:00:00Z', end_time: '2025-12-17T15:00:00Z', meeting_room: 2, meeting_room_name: 'Room B', user: { id: 2, username: 'anotheruser', real_name: 'Another User', phone_numbers: [{ number: '0987654321' }] } },
    ],
  },
};

const mockUser = { id: 1, username: 'testuser', role: 'user', real_name: 'Test User', phone_numbers: [{ number: '1234567890' }] };
const mockAdmin = { id: 3, username: 'adminuser', role: 'admin', real_name: 'Admin User', phone_numbers: [{ number: '111222333' }] };

const renderWithAuth = (ui, { providerProps, ...renderOptions }) => {
  return render(
    <MemoryRouter>
      <AuthContext.Provider value={providerProps}>{ui}</AuthContext.Provider>
    </MemoryRouter>,
    renderOptions
  );
};

describe('MeetingRoomBookingPage', () => {
  beforeAll(() => {
    // Set a fixed date for all tests to ensure the calendar view is consistent
    jest.useFakeTimers('modern');
    jest.setSystemTime(new Date('2025-12-16T00:00:00Z'));
  });

  beforeEach(() => {
    meetingRoomApi.getMeetingRooms.mockResolvedValue(mockMeetingRooms);
    meetingRoomApi.getMeetingRoomBookings.mockResolvedValue(mockBookings);
    meetingRoomApi.createMeetingRoomBooking.mockResolvedValue({ data: { id: 3, ...mockBookings.data.results[0] } });
    meetingRoomApi.updateMeetingRoomBooking.mockResolvedValue({ data: { id: 1, title: 'Updated Meeting' } });
    meetingRoomApi.deleteMeetingRoomBooking.mockResolvedValue({ status: 204 });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  afterAll(() => {
    jest.useRealTimers();
  });

  test('renders the component, fetches data, and displays bookings', async () => {
    renderWithAuth(<MeetingRoomBookingPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

    expect(screen.getByRole('heading', { name: /会议室预约/i })).toBeInTheDocument();
    
    await waitFor(() => {
      expect(meetingRoomApi.getMeetingRooms).toHaveBeenCalledTimes(1);
      expect(meetingRoomApi.getMeetingRoomBookings).toHaveBeenCalledTimes(1);
    });

    // Check if bookings are rendered
    expect(await screen.findByTestId('booking-event-1')).toBeInTheDocument();
    expect(await screen.findByTestId('booking-event-2')).toBeInTheDocument();
  });

  test('opens a modal to create a new booking when a slot is selected', async () => {
    renderWithAuth(<MeetingRoomBookingPage />, { providerProps: { user: mockUser, isAuthenticated: true } });
    
    // Wait for data to load
    await screen.findByTestId('booking-event-1');

    // Simulate clicking on a time slot. We target a specific time slot element.
    // This is brittle, but a common way to test react-big-calendar slot selection.
    // Simulate clicking on a time slot. We find a clickable element representing a time.
    const timeSlotButton = screen.getAllByRole('button', { name: /9:00 AM/i })[0];
    fireEvent.click(timeSlotButton);

    await waitFor(() => {
        expect(screen.getByRole('dialog', { name: /新建会议室预约/i })).toBeInTheDocument();
    });

    // Fill the form
    fireEvent.change(screen.getByLabelText(/主题/i), { target: { value: 'New Important Meeting' } });
    
    // Antd Select requires more specific interaction
    fireEvent.mouseDown(screen.getByLabelText(/会议室/i));
    fireEvent.click(await screen.findByText('Room A'));

    fireEvent.click(screen.getByRole('button', { name: /创建/i }));

    await waitFor(() => {
      expect(meetingRoomApi.createMeetingRoomBooking).toHaveBeenCalledWith(expect.objectContaining({
        title: 'New Important Meeting',
        meeting_room: 1,
      }));
    });

    expect(await screen.findByText(/预约创建成功！/i)).toBeInTheDocument();
  });

  test('opens detail modal, then edit modal, and updates a booking', async () => {
    renderWithAuth(<MeetingRoomBookingPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

    const event = await screen.findByTestId('booking-event-1');
    fireEvent.click(event);

    // Detail modal should open first
    const detailModal = await screen.findByRole('dialog', { name: /预约详情/i });
    expect(detailModal).toBeInTheDocument();
    expect(screen.getByText('Team Meeting')).toBeInTheDocument();

    // Click edit button in detail modal
    fireEvent.click(screen.getByRole('button', { name: /编辑/i }));

    // Now the edit modal should open
    const editModal = await screen.findByRole('dialog', { name: /编辑会议室预约/i });
    expect(editModal).toBeInTheDocument();
    expect(screen.getByLabelText(/主题/i)).toHaveValue('Team Meeting');

    // Edit the form
    fireEvent.change(screen.getByLabelText(/主题/i), { target: { value: 'Updated Meeting Title' } });
    fireEvent.click(screen.getByRole('button', { name: /更新/i }));

    await waitFor(() => {
      expect(meetingRoomApi.updateMeetingRoomBooking).toHaveBeenCalledWith(1, expect.objectContaining({
        title: 'Updated Meeting Title',
      }));
    });
    
    expect(await screen.findByText(/预约更新成功！/i)).toBeInTheDocument();
  });

  test('deletes a booking from the edit modal', async () => {
    renderWithAuth(<MeetingRoomBookingPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

    const event = await screen.findByTestId('booking-event-1');
    fireEvent.click(event);

    // Open detail modal, then edit modal
    await screen.findByRole('dialog', { name: /预约详情/i });
    fireEvent.click(screen.getByRole('button', { name: /编辑/i }));
    
    await screen.findByRole('dialog', { name: /编辑会议室预约/i });

    // Click delete button
    fireEvent.click(screen.getByRole('button', { name: /删除/i }));

    // Confirm deletion in Popconfirm
    const confirmButton = await screen.findByRole('button', { name: /是/i });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(meetingRoomApi.deleteMeetingRoomBooking).toHaveBeenCalledWith(1);
    });

    expect(await screen.findByText(/预约删除成功！/i)).toBeInTheDocument();
  });

  test('user cannot see edit button for other users bookings', async () => {
    renderWithAuth(<MeetingRoomBookingPage />, { providerProps: { user: mockUser, isAuthenticated: true } });

    const event = await screen.findByTestId('booking-event-2');
    fireEvent.click(event);

    // Detail modal should open
    const detailModal = await screen.findByRole('dialog', { name: /预约详情/i });
    expect(detailModal).toBeInTheDocument();
    
    // The "Edit" button should NOT be present
    expect(screen.queryByRole('button', { name: /编辑/i })).not.toBeInTheDocument();
  });

  test('admin can see edit button and delete other users bookings', async () => {
    renderWithAuth(<MeetingRoomBookingPage />, { providerProps: { user: mockAdmin, isAuthenticated: true } });

    const event = await screen.findByTestId('booking-event-2');
    fireEvent.click(event);

    // Detail modal opens
    await screen.findByRole('dialog', { name: /预约详情/i });
    
    // Admin should see the edit button
    const editButton = screen.getByRole('button', { name: /编辑/i });
    expect(editButton).toBeInTheDocument();
    fireEvent.click(editButton);

    // Edit modal opens
    await screen.findByRole('dialog', { name: /编辑会议室预约/i });
    expect(screen.getByLabelText(/主题/i)).toHaveValue('Project Sync');

    // Test deletion
    fireEvent.click(screen.getByRole('button', { name: /删除/i }));
    fireEvent.click(await screen.findByRole('button', { name: /是/i }));

    await waitFor(() => {
      expect(meetingRoomApi.deleteMeetingRoomBooking).toHaveBeenCalledWith(2);
    });
    
    expect(await screen.findByText(/预约删除成功！/i)).toBeInTheDocument();
  });
});