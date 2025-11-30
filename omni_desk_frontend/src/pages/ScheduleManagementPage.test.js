import React from 'react';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ScheduleManagementPage from './ScheduleManagementPage';
import { scheduleApi } from '../api/scheduleApi';
import { getAllPersonnel, getPositions } from '../api/personnelApi';
import { getPersonnelSequences, getLeaderSequences } from '../api/sequenceApi';

// Mock APIs
jest.mock('../api/scheduleApi');
jest.mock('../api/personnelApi');
jest.mock('../api/sequenceApi');

// Mock child components
jest.mock('../components/Schedule/PersonnelSequenceModal', () => (props) => <div data-testid="personnel-sequence-modal-mock" />);
jest.mock('../components/Schedule/WeeklyLeaderDisplay', () => (props) => <div data-testid="weekly-leader-display-mock" />);
jest.mock('../components/Schedule/MonthlyLeaderSidebar', () => (props) => <div data-testid="monthly-leader-sidebar-mock" />);

const mockSchedules = [
  { id: 1, duty_date: '2025-11-10', duty_person: { id: 1, name: 'Alice' }, duty_leader: { id: 101, name: 'Leader A' } },
  { id: 2, duty_date: '2025-11-15', duty_person: { id: 2, name: 'Bob' }, duty_leader: { id: 102, name: 'Leader B' } },
];

const mockPersonnel = [
  { id: 1, name: 'Alice', position: 1, position_name: 'Dev' },
  { id: 2, name: 'Bob', position: 1, position_name: 'Dev' },
  { id: 3, name: 'Charlie', position: 2, position_name: 'QA' },
  { id: 101, name: 'Leader A', position: 1, position_name: 'Dev' },
  { id: 102, name: 'Leader B', position: 2, position_name: 'QA' },
];

const mockPositions = { results: [{ id: 1, name: 'Dev' }, { id: 2, name: 'QA' }] };

const mockSequences = {
  data: {
    results: [
      { id: 1, name: 'Seq A', personnel_details: [{ id: 1, name: 'Alice' }, { id: 2, name: 'Bob' }], holiday_personnel_details: [{ id: 3, name: 'Charlie' }] },
      { id: 2, name: 'Seq B', personnel_details: [{ id: 101, name: 'Leader A' }, { id: 102, name: 'Leader B' }], holiday_personnel_details: [] },
    ],
  },
};

// Mock FullCalendar
const mockEventClick = jest.fn();
jest.mock('@fullcalendar/react', () => {
    const React = require('react');
    return {
        __esModule: true,
        default: React.forwardRef((props, ref) => {
            React.useImperativeHandle(ref, () => ({
                getApi: () => ({
                    getEventById: (id) => mockSchedules.find(s => s.id.toString() === id),
                }),
            }));
            return (
                <div data-testid="fullcalendar-mock">
                    {props.events.map(event => (
                        <div key={event.id} data-testid={`event-${event.id}`} onClick={() => mockEventClick({ event })}>
                            {event.title}
                        </div>
                    ))}
                </div>
            );
        }),
    };
});


describe('ScheduleManagementPage', () => {
  beforeEach(() => {
    jest.setTimeout(30000);
    scheduleApi.getSchedules.mockResolvedValue(mockSchedules);
    getAllPersonnel.mockResolvedValue(mockPersonnel);
    getPositions.mockResolvedValue(mockPositions);
    getPersonnelSequences.mockResolvedValue(mockSequences);
    getLeaderSequences.mockResolvedValue(mockSequences);
    scheduleApi.createSchedule.mockResolvedValue({ success: true });
    scheduleApi.updateSchedule.mockResolvedValue({ success: true });
    scheduleApi.deleteSchedule.mockResolvedValue({ success: true });
    scheduleApi.generateSchedules.mockResolvedValue({ success: true });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  const renderComponent = async () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <ScheduleManagementPage />
      </QueryClientProvider>
    );
    await waitFor(() => expect(getAllPersonnel).toHaveBeenCalled());
    await screen.findByText('Alice');
  };

  test('renders and fetches initial data', async () => {
    await renderComponent();
    expect(screen.getByText('排班管理')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
  });

  test('opens add modal, submits, and closes', async () => {
    await renderComponent();
    await userEvent.click(screen.getByTestId('add-schedule-button'));
    const dialog = await screen.findByTestId('schedule-modal');

    await userEvent.type(within(dialog).getByLabelText('值班日期'), '2025-11-26');
    
    await userEvent.click(within(dialog).getByLabelText('值班人员'));
    await waitFor(async () => {
      const aliceOptions = await screen.findAllByText('Alice (Dev)');
      await userEvent.click(aliceOptions[0]);
    });

    await userEvent.click(within(dialog).getByLabelText('值班领导'));
    await waitFor(async () => {
      const leaderAOptions = await screen.findAllByText('Leader A (Dev)');
      await userEvent.click(leaderAOptions[0]);
    });

    await userEvent.click(screen.getByTestId('schedule-modal-ok-button'));

    await waitFor(() => {
      expect(scheduleApi.createSchedule).toHaveBeenCalledWith({
        date: '2025-11-26',
        duty_person_id: 1,
        duty_leader_id: 101,
      });
    });
  });

  test('opens edit modal, submits, and closes', async () => {
    await renderComponent();
    fireEvent.click(screen.getByTestId('event-1'));
    const dialog = await screen.findByTestId('schedule-modal');

    await waitFor(() => {
      expect(within(dialog).getByLabelText('值班日期')).toHaveValue('2025-11-10');
    });

    await userEvent.click(within(dialog).getByLabelText('值班人员'));
    await waitFor(async () => {
      const bobOptions = await screen.findAllByText('Bob (Dev)');
      await userEvent.click(bobOptions[0]);
    });

    await userEvent.click(within(dialog).getByLabelText('值班领导'));
    await waitFor(async () => {
      const leaderBOptions = await screen.findAllByText('Leader B (QA)');
      await userEvent.click(leaderBOptions[0]);
    });

    await userEvent.click(screen.getByTestId('schedule-modal-ok-button'));

    await waitFor(() => {
      expect(scheduleApi.updateSchedule).toHaveBeenCalledWith(1, expect.objectContaining({
        duty_person_id: 2,
        duty_leader_id: 102,
      }));
    });
  });

  test('deletes a schedule', async () => {
    await renderComponent();
    await userEvent.click(await screen.findByTestId('delete-schedule-button-1'));
    await userEvent.click(await screen.findByRole('button', { name: /确 定/ }));

    await waitFor(() => {
      expect(scheduleApi.deleteSchedule).toHaveBeenCalledWith(1);
    });
  });

  test('opens generate schedule modal, submits, and closes', async () => {
    await renderComponent();
    await userEvent.click(screen.getByTestId('generate-schedule-button'));
    const dialog = await screen.findByTestId('generate-schedule-modal');

    await userEvent.type(screen.getByTestId('generate-schedule-start-date'), '2025-12-01');
    await userEvent.type(screen.getByTestId('generate-schedule-duration-days'), '10');

    await userEvent.click(screen.getByTestId('generate-schedule-workday-personnel-sequence'));
    await waitFor(async () => {
      const seqAWorkdayOptions = await screen.findAllByText(/Seq A \(工作日: Alice, Bob\)/);
      await userEvent.click(seqAWorkdayOptions[0]);
    });
    
    await userEvent.click(screen.getByTestId('generate-schedule-holiday-personnel-sequence'));
    await waitFor(async () => {
      const seqAHolidayOptions = await screen.findAllByText(/Seq A \(节假日: Charlie\)/);
      await userEvent.click(seqAHolidayOptions[0]);
    });

    await userEvent.click(screen.getByTestId('generate-schedule-start-personnel'));
    await waitFor(async () => {
      const aliceOptionsGen = await screen.findAllByRole('option', { name: 'Alice' });
      await userEvent.click(aliceOptionsGen[0]);
    });

    await userEvent.click(screen.getByTestId('generate-schedule-start-holiday-personnel'));
    await waitFor(async () => {
      const charlieOptionsGen = await screen.findAllByRole('option', { name: 'Charlie' });
      await userEvent.click(charlieOptionsGen[0]);
    });

    await userEvent.click(screen.getByTestId('generate-schedule-leader-sequence'));
    await waitFor(async () => {
      const seqBOptions = await screen.findAllByText(/Seq B \(Leader A, Leader B\)/);
      await userEvent.click(seqBOptions[0]);
    });

    await userEvent.click(within(dialog).getByRole('button', { name: 'OK' }));

    await waitFor(() => {
      expect(scheduleApi.generateSchedules).toHaveBeenCalledWith(expect.objectContaining({
        workday_personnel_sequence_id: 1,
        holiday_personnel_sequence_id: 1,
        start_personnel_id: 1,
        start_holiday_personnel_id: 3,
        leader_sequence_id: 2,
      }));
    });
  });
});