import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
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
jest.mock('../components/Schedule/PersonnelSequenceModal', () => {
    const MockComponent = () => <div data-testid="personnel-sequence-modal-mock" />;
    MockComponent.displayName = 'PersonnelSequenceModal';
    return MockComponent;
});
jest.mock('../components/Schedule/WeeklyLeaderDisplay', () => {
    const MockComponent = () => <div data-testid="weekly-leader-display-mock" />;
    MockComponent.displayName = 'WeeklyLeaderDisplay';
    return MockComponent;
});
jest.mock('../components/Schedule/MonthlyLeaderSidebar', () => {
    const MockComponent = () => <div data-testid="monthly-leader-sidebar-mock" />;
    MockComponent.displayName = 'MonthlyLeaderSidebar';
    return MockComponent;
});

const mockSchedules = [
  { id: 1, duty_date: '2025-11-10', duty_person: { id: 1, name: 'Alice' }, duty_leader: { id: 101, name: 'Leader A' } },
  { id: 2, duty_date: '2025-11-15', duty_person: { id: 2, name: 'Bob' }, duty_leader: { id: 102, name: 'Leader B' } },
];

const mockPersonnel = [
  { id: 1, name: 'Alice', position: 1, position_name: 'Dev', phone_numbers: [{ number: '111' }] },
  { id: 2, name: 'Bob', position: 1, position_name: 'Dev', phone_numbers: [] },
  { id: 3, name: 'Charlie', position: 2, position_name: 'QA', phone_numbers: [] },
  { id: 101, name: 'Leader A', position: 1, position_name: 'Dev', phone_numbers: [{ number: '222' }] },
  { id: 102, name: 'Leader B', position: 2, position_name: 'QA', phone_numbers: [] },
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
jest.mock('@fullcalendar/react', () => {
    const React = require('react');
    const PropTypes = require('prop-types');
    const FullCalendar = React.forwardRef((props, ref) => {
        React.useImperativeHandle(ref, () => ({
            getApi: () => ({
                getEventById: (id) => mockSchedules.find(s => s.id.toString() === id),
                changeView: jest.fn(),
            }),
        }));
        return (
            <div data-testid="fullcalendar-mock">
                {props.events.map(event => (
                    <div key={event.id} data-testid={`event-${event.id}`} onClick={() => props.eventClick({ event })}>
                        {event.title}
                    </div>
                ))}
            </div>
        );
    });

    FullCalendar.displayName = 'FullCalendar';

    FullCalendar.propTypes = {
        events: PropTypes.arrayOf(PropTypes.shape({
            id: PropTypes.any.isRequired,
            title: PropTypes.string,
        })).isRequired,
        eventClick: PropTypes.func,
    };
    
    FullCalendar.defaultProps = {
      eventClick: () => {},
    };

    return {
        __esModule: true,
        default: FullCalendar,
    };
});


describe('ScheduleManagementPage', () => {
  beforeEach(() => {
    jest.setTimeout(30000);
    scheduleApi.getSchedules.mockResolvedValue(mockSchedules);
    getAllPersonnel.mockResolvedValue({ results: mockPersonnel });
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
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
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
    const user = userEvent.setup();
    await renderComponent();
    await user.click(screen.getByTestId('add-schedule-button'));
    const dialog = await screen.findByTestId('schedule-modal');

    const dateInput = within(dialog).getByLabelText('值班日期');
    await user.click(dateInput);
    await user.click(await screen.findByTitle('2025-11-26'));

    await user.click(within(dialog).getByTestId('schedule-modal-duty-person-select'));
    await user.click(await screen.findByRole('option', { name: 'Alice (Dev)' }));

    await user.click(within(dialog).getByTestId('schedule-modal-duty-leader-select'));
    await user.click(await screen.findByRole('option', { name: 'Leader A (Dev)' }));

    await user.click(screen.getByTestId('schedule-modal-ok-button'));

    await waitFor(() => {
      expect(scheduleApi.createSchedule).toHaveBeenCalledWith({
        date: '2025-11-26',
        duty_person_id: 1,
        duty_leader_id: 101,
      });
    });
  });

  test('opens edit modal, submits, and closes', async () => {
    const user = userEvent.setup();
    await renderComponent();
    await user.click(screen.getByTestId('event-1'));
    const dialog = await screen.findByTestId('schedule-modal');

    await waitFor(() => {
      expect(within(dialog).getByLabelText('值班日期')).toHaveValue('2025-11-10');
    });

    await user.click(within(dialog).getByTestId('schedule-modal-duty-person-select'));
    await user.click(await screen.findByRole('option', { name: 'Bob (Dev)' }));

    await user.click(within(dialog).getByTestId('schedule-modal-duty-leader-select'));
    await user.click(await screen.findByRole('option', { name: 'Leader B (QA)' }));

    await user.click(screen.getByTestId('schedule-modal-ok-button'));

    await waitFor(() => {
      expect(scheduleApi.updateSchedule).toHaveBeenCalledWith(1, expect.objectContaining({
        duty_person_id: 2,
        duty_leader_id: 102,
      }));
    });
  });

  test('deletes a schedule from list view', async () => {
    const user = userEvent.setup();
    await renderComponent();

    await user.click(screen.getByRole('radio', { name: '列表' }));

    const deleteButton = await screen.findByTestId('delete-schedule-button-1');
    await user.click(deleteButton);

    const confirmButton = await screen.findByRole('button', { name: /确 定/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(scheduleApi.deleteSchedule).toHaveBeenCalledWith(1);
    });
  });

  test('opens generate schedule modal, submits, and closes', async () => {
    const user = userEvent.setup();
    await renderComponent();
    await user.click(screen.getByTestId('generate-schedule-button'));
    const dialog = await screen.findByTestId('generate-schedule-modal');

    await user.click(within(dialog).getByLabelText('起始日期'));
    await user.click(await screen.findByTitle('2025-12-01'));

    await user.clear(screen.getByTestId('generate-schedule-duration-days'));
    await user.type(screen.getByTestId('generate-schedule-duration-days'), '10');

    await user.click(screen.getByTestId('generate-schedule-workday-personnel-sequence'));
    await user.click(await screen.findByText(/Seq A \(工作日: Alice, Bob\)/));

    await user.click(screen.getByTestId('generate-schedule-holiday-personnel-sequence'));
    await user.click(await screen.findByText(/Seq A \(节假日: Charlie\)/));

    await user.click(screen.getByTestId('generate-schedule-start-personnel'));
    await user.click(await screen.findByRole('option', { name: 'Alice' }));

    await user.click(screen.getByTestId('generate-schedule-start-holiday-personnel'));
    await user.click(await screen.findByRole('option', { name: 'Charlie' }));

    await user.click(screen.getByTestId('generate-schedule-leader-sequence'));
    await user.click(await screen.findByText(/Seq B \(Leader A, Leader B\)/));

    await user.click(within(dialog).getByRole('button', { name: 'OK' }));

    await waitFor(() => {
      expect(scheduleApi.generateSchedules).toHaveBeenCalledWith(expect.objectContaining({
        start_date: '2025-12-01',
        duration_days: '10',
        workday_personnel_sequence_id: 1,
        holiday_personnel_sequence_id: 1,
        start_personnel_id: 1,
        start_holiday_personnel_id: 3,
        leader_sequence_id: 2,
      }));
    });
  });
});