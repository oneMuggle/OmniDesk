import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import moment from 'moment';
import ScheduleManagementPage from './ScheduleManagementPage';
import { scheduleApi } from '../api/scheduleApi';
import { getAllPersonnel, getPositions } from '../api/personnelApi';
import { getPersonnelSequences, getLeaderSequences } from '../api/sequenceApi';

// Mock libraries with browser dependencies
jest.mock('jspdf');
jest.mock('html2canvas');

// Mock APIs
jest.mock('../api/scheduleApi');
jest.mock('../api/personnelApi');
jest.mock('../api/sequenceApi');

const mockSchedules = [
  { id: 1, duty_date: '2025-11-10', duty_person: { id: 1, name: 'Alice' }, duty_leader: { id: 101, name: 'Leader A' } },
  { id: 2, duty_date: '2025-11-15', duty_person: { id: 2, name: 'Bob' }, duty_leader: { id: 102, name: 'Leader B' } },
];

const mockPersonnel = [
  { id: 1, name: 'Alice', position: 1, position_name: 'Dev' },
  { id: 2, name: 'Bob', position: 1, position_name: 'Dev' },
  { id: 101, name: 'Leader A', position: 1, position_name: 'Dev' },
  { id: 102, name: 'Leader B', position: 2, position_name: 'QA' },
];

const mockPositions = { results: [{ id: 1, name: 'Dev' }, { id: 2, name: 'QA' }] };
const mockSequences = {
  data: {
    results: [
      { id: 1, name: 'Seq A', personnel_details: [{ id: 1, name: 'Alice' }, { id: 2, name: 'Bob' }] },
      { id: 2, name: 'Seq B', personnel_details: [{ id: 101, name: 'Leader A' }, { id: 102, name: 'Leader B' }] },
    ],
  },
};

describe('ScheduleManagementPage', () => {
  beforeEach(() => {
    scheduleApi.getSchedules.mockResolvedValue(mockSchedules);
    getAllPersonnel.mockResolvedValue(mockPersonnel);
    getPositions.mockResolvedValue(mockPositions);
    getPersonnelSequences.mockResolvedValue(mockSequences);
    getLeaderSequences.mockResolvedValue(mockSequences);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  const renderComponent = async () => {
    render(<ScheduleManagementPage />);
    await waitFor(() => expect(scheduleApi.getSchedules).toHaveBeenCalled());
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

    fireEvent.click(screen.getByTestId('add-schedule-button'));
    const dialog = await screen.findByTestId('schedule-modal');

    fireEvent.change(within(dialog).getByLabelText('值班日期'), { target: { value: '2025-11-26' } });
    
    fireEvent.mouseDown(within(dialog).getByLabelText('值班人员'));
    fireEvent.click(await screen.findByRole('option', { name: 'Alice (Dev)' }));

    fireEvent.mouseDown(within(dialog).getByLabelText('值班领导'));
    fireEvent.click(await screen.findByRole('option', { name: 'Leader A (Dev)' }));

    scheduleApi.createSchedule.mockResolvedValue({ success: true });

    fireEvent.click(screen.getByTestId('schedule-modal-ok-button'));

    await waitFor(() => {
      expect(scheduleApi.createSchedule).toHaveBeenCalledWith({
        date: '2025-11-26',
        duty_person_id: 1,
        duty_leader_id: 101,
      });
    });

    await waitFor(() => {
      expect(screen.queryByTestId('schedule-modal')).not.toBeInTheDocument();
    });
  });

  test('opens edit modal, submits, and closes', async () => {
    await renderComponent();

    const editButton = await screen.findByTestId('edit-schedule-button-1');
    fireEvent.click(editButton);
    const dialog = await screen.findByTestId('schedule-modal');

    await waitFor(() => {
        expect(within(dialog).getByLabelText('值班日期').value).toBe('2025-11-10');
    });

    // Re-select values to ensure form is valid
    fireEvent.mouseDown(within(dialog).getByLabelText('值班人员'));
    fireEvent.click(await screen.findByRole('option', { name: 'Bob (Dev)' }));

    fireEvent.mouseDown(within(dialog).getByLabelText('值班领导'));
    fireEvent.click(await screen.findByRole('option', { name: 'Leader B (QA)' }));

    scheduleApi.updateSchedule.mockResolvedValue({ success: true });

    fireEvent.click(screen.getByTestId('schedule-modal-ok-button'));

    await waitFor(() => {
      expect(scheduleApi.updateSchedule).toHaveBeenCalledWith(1, expect.objectContaining({
        duty_person_id: 2,
        duty_leader_id: 102,
      }));
    });

    await waitFor(() => {
      expect(screen.queryByTestId('schedule-modal')).not.toBeInTheDocument();
    });
  });

  test('deletes a schedule', async () => {
    await renderComponent();

    scheduleApi.deleteSchedule.mockResolvedValue({ success: true });

    const deleteButton = await screen.findByTestId('delete-schedule-button-1');
    fireEvent.click(deleteButton);

    const confirmButton = await screen.findByRole('button', { name: '确定' });
    await userEvent.click(confirmButton);

    await waitFor(() => {
      expect(scheduleApi.deleteSchedule).toHaveBeenCalledWith(1);
    });
  });

  test('opens generate schedule modal, submits, and closes', async () => {
    await renderComponent();

    fireEvent.click(screen.getByTestId('generate-schedule-button'));
    const dialog = await screen.findByTestId('generate-schedule-modal');

    fireEvent.change(screen.getByTestId('generate-schedule-start-date'), { target: { value: '2025-12-01' } });
    fireEvent.change(screen.getByTestId('generate-schedule-duration-days'), { target: { value: '10' } });

    fireEvent.mouseDown(screen.getByTestId('generate-schedule-personnel-sequence'));
    fireEvent.click(await screen.findByText(/Seq A/));
    
    fireEvent.mouseDown(screen.getByTestId('generate-schedule-leader-sequence'));
    fireEvent.click(await screen.findByText(/Seq B/));

    scheduleApi.generateSchedules.mockResolvedValue({ success: true });

    fireEvent.click(within(dialog).getByRole('button', { name: 'OK' }));

    await waitFor(() => {
      expect(scheduleApi.generateSchedules).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.queryByTestId('generate-schedule-modal')).not.toBeInTheDocument();
    });
  });
});