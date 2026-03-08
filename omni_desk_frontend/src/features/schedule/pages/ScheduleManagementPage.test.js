import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import ScheduleManagementPage from './ScheduleManagementPage';
import { scheduleApi } from '../api/scheduleApi';
import { getAllPersonnel, getPositions } from '../../personnel/api/personnelApi';
import { getPersonnelSequences, getLeaderSequences } from '../../../shared/api/sequenceApi';

// Mock external libraries
jest.mock('jspdf');
jest.mock('html2canvas');

// Mock API modules at the top level
jest.mock('../api/scheduleApi');
jest.mock('../../personnel/api/personnelApi');
jest.mock('../../../shared/api/sequenceApi');

// Use jest.mocked for typed mock functions
const mockedGetSchedules = jest.mocked(scheduleApi.getSchedules);
const mockedGenerateSchedules = jest.mocked(scheduleApi.generateSchedules);
const mockedGetAllPersonnel = jest.mocked(getAllPersonnel);
const mockedGetPositions = jest.mocked(getPositions);
const mockedGetPersonnelSequences = jest.mocked(getPersonnelSequences);
const mockedGetLeaderSequences = jest.mocked(getLeaderSequences);

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
    mockedGetSchedules.mockResolvedValue(mockSchedules);
    mockedGetAllPersonnel.mockResolvedValue(mockPersonnel);
    mockedGetPositions.mockResolvedValue(mockPositions);
    mockedGetPersonnelSequences.mockResolvedValue(mockPersonnelSequences);
    mockedGetLeaderSequences.mockResolvedValue(mockLeaderSequences);
    mockedGenerateSchedules.mockResolvedValue({ success: true });
  });

  test('renders calendar view by default and displays schedule information', async () => {
    renderWithProvider(<ScheduleManagementPage />);
    
    expect(screen.getByRole('heading', { name: '排班管理' })).toBeInTheDocument();

    // Check for calendar view components by their accessible roles or text
    // Instead of a mock, we check for elements rendered by the actual FullCalendar component
    await waitFor(() => {
      // The calendar toolbar should be visible
      expect(screen.getByRole('button', { name: 'today' })).toBeInTheDocument();
    });

    // Check for an event rendered on the calendar
    expect(await screen.findByText('Alice')).toBeInTheDocument();
    expect(await screen.findByText('Leader A')).toBeInTheDocument();
    
    // List view table should not be visible
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  test('switches to list view and displays schedule table', async () => {
    const user = userEvent.setup();
    renderWithProvider(<ScheduleManagementPage />);

    // Wait for initial data to load in calendar view
    expect(await screen.findByText('Alice')).toBeInTheDocument();

    // Switch to list view using a semantic role query
    const listRadioButton = screen.getByRole('radio', { name: '列表' });
    await user.click(listRadioButton);

    // Check for the table and its content
    const table = await screen.findByRole('table');
    expect(table).toBeInTheDocument();
    
    // Check for data within the table
    expect(await screen.findByRole('cell', { name: 'Alice' })).toBeInTheDocument();
    expect(await screen.findByRole('cell', { name: 'Leader B' })).toBeInTheDocument();

    // Calendar view's specific controls should not be visible
    expect(screen.queryByRole('button', { name: 'today' })).not.toBeInTheDocument();
  });

  test('opens generate schedule modal and switches generation mode', async () => {
    const user = userEvent.setup();
    renderWithProvider(<ScheduleManagementPage />);

    // Open the generate modal
    const generateButton = screen.getByRole('button', { name: /生成排班/i });
    await user.click(generateButton);

    const modal = await screen.findByRole('dialog', { name: /生成排班/i });
    expect(modal).toBeInTheDocument();

    // Check default mode is "by days" using label text
    expect(screen.getByLabelText('开始日期')).toBeInTheDocument();
    expect(screen.getByLabelText('持续天数')).toBeInTheDocument();
    expect(screen.queryByLabelText('目标月份')).not.toBeInTheDocument();

    // Switch to "by month"
    const monthRadioButton = screen.getByRole('radio', { name: '按月份' });
    await user.click(monthRadioButton);

    // Check for month picker and that day inputs are gone
    expect(await screen.findByLabelText('目标月份')).toBeInTheDocument();
    expect(screen.queryByLabelText('开始日期')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('持续天数')).not.toBeInTheDocument();
  });
});