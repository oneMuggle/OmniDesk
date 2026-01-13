import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import ScheduleManagementPage from './ScheduleManagementPage';
import { scheduleApi } from '../api/scheduleApi';
import { getAllPersonnel, getPositions } from '../../personnel/api/personnelApi';
import { getPersonnelSequences, getLeaderSequences } from '../../../shared/api/sequenceApi';

// Mock heavy components
jest.mock('@fullcalendar/react', () => function FullCalendarMock(props) {
  return <div data-testid="fullcalendar-mock">{JSON.stringify(props)}</div>;
});
jest.mock('../../../shared/components/Schedule/MonthlyLeaderSidebar', () => function MonthlyLeaderSidebarMock() {
  return <div data-testid="monthly-leader-sidebar-mock"></div>;
});
jest.mock('jspdf');
jest.mock('html2canvas');

// Mock API modules
jest.mock('../api/scheduleApi');
jest.mock('../../personnel/api/personnelApi');
jest.mock('../../../shared/api/sequenceApi');

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

const renderWithProvider = (ui) => {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ConfigProvider>
          {ui}
        </ConfigProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

const mockSchedules = [
  { id: 1, duty_date: '2024-01-01', duty_person: { id: 1, name: 'Alice', phone_numbers: [{ number: '111' }] }, duty_leader: { id: 101, name: 'Leader A', phone_numbers: [{ number: '999' }] } },
  { id: 2, duty_date: '2024-01-02', duty_person: { id: 2, name: 'Bob', phone_numbers: [{ number: '222' }] }, duty_leader: { id: 102, name: 'Leader B', phone_numbers: [{ number: '888' }] } },
];
const mockPersonnel = { data: { results: [{ id: 1, name: 'Alice', position: 1, position_name: 'Dev' }, { id: 2, name: 'Bob', position: 2, position_name: 'QA' }] } };
const mockPositions = { data: { results: [{ id: 1, name: 'Dev' }, { id: 2, name: 'QA' }] } };
const mockPersonnelSequences = { data: { results: [{ id: 1, name: 'Seq A', personnel_details: [{ id: 1, name: 'Alice' }] }] } };
const mockLeaderSequences = { data: { results: [{ id: 1, name: 'Leader Seq A', personnel_details: [{ id: 101, name: 'Leader A' }] }] } };

describe('ScheduleManagementPage', () => {
  beforeEach(() => {
    // Reset mocks before each test
    queryClient.clear();
    scheduleApi.getSchedules.mockResolvedValue(mockSchedules);
    getAllPersonnel.mockResolvedValue(mockPersonnel);
    getPositions.mockResolvedValue(mockPositions);
    getPersonnelSequences.mockResolvedValue(mockPersonnelSequences);
    getLeaderSequences.mockResolvedValue(mockLeaderSequences);
    scheduleApi.generateSchedules.mockResolvedValue({ success: true });
  });

  test('renders calendar view by default', async () => {
    renderWithProvider(<ScheduleManagementPage />);
    
    // Check for page title
    expect(screen.getByText('排班管理')).toBeInTheDocument();

    // Check for calendar view components
    await waitFor(() => {
      expect(screen.getByTestId('fullcalendar-mock')).toBeInTheDocument();
    });
    expect(screen.getByTestId('monthly-leader-sidebar-mock')).toBeInTheDocument();
    
    // List view should not be visible
    expect(screen.queryByTestId('schedule-table')).not.toBeInTheDocument();
  });

  test('switches to list view and displays schedule table', async () => {
    renderWithProvider(<ScheduleManagementPage />);

    // Wait for initial data to load
    await waitFor(() => {
      expect(screen.getByTestId('fullcalendar-mock')).toBeInTheDocument();
    });

    // Switch to list view
    const listRadioButton = screen.getByRole('radio', { name: '列表' });
    fireEvent.click(listRadioButton);

    // Check for table and data
    await waitFor(() => {
      expect(screen.getByTestId('schedule-table')).toBeInTheDocument();
    });
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Leader B')).toBeInTheDocument();

    // Calendar view should not be visible
    expect(screen.queryByTestId('fullcalendar-mock')).not.toBeInTheDocument();
  });

  test('opens generate schedule modal and switches generation mode', async () => {
    renderWithProvider(<ScheduleManagementPage />);

    // Wait for initial data to load
    await waitFor(() => {
        expect(screen.getByTestId('generate-schedule-button')).toBeInTheDocument();
    });

    // Open the generate modal
    const generateButton = screen.getByTestId('generate-schedule-button');
    fireEvent.click(generateButton);

    await waitFor(() => {
      expect(screen.getByTestId('generate-schedule-modal')).toBeInTheDocument();
    });

    // Check default mode is "by days"
    expect(screen.getByTestId('generate-schedule-start-date')).toBeInTheDocument();
    expect(screen.getByTestId('generate-schedule-duration-days')).toBeInTheDocument();
    expect(screen.queryByTestId('generate-schedule-target-month')).not.toBeInTheDocument();

    // Switch to "by month"
    const monthRadioButton = screen.getByRole('radio', { name: '按月份' });
    fireEvent.click(monthRadioButton);

    // Check for month picker and that day inputs are gone
    await waitFor(() => {
        expect(screen.getByTestId('generate-schedule-target-month')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('generate-schedule-start-date')).not.toBeInTheDocument();
    expect(screen.queryByTestId('generate-schedule-duration-days')).not.toBeInTheDocument();
  });
});