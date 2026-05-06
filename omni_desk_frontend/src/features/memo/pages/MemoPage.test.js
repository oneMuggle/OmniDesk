import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter as Router } from 'react-router-dom';
import moment from 'moment';
import MemoPage from './MemoPage';
import { useMemoData } from '../hooks/useMemoData';
import { useCalendar } from '../../schedule/hooks/useCalendar';

jest.mock('../hooks/useMemoData');
jest.mock('../../schedule/hooks/useCalendar');
jest.mock('../components/MiniCalendar', () => {
  const MockMiniCalendar = ({ memos }) => (
    <div data-testid="mini-calendar">
      {memos?.map(m => <div key={m.id}>{m.title}</div>)}
    </div>
  );
  MockMiniCalendar.displayName = 'MiniCalendar';
  return MockMiniCalendar;
});

describe('MemoPage Component', () => {
  const MOCK_DATE_NOW = new Date('2025-10-27T10:00:00.000Z').getTime();
  let dateNowSpy;
  let mockMemos;
  let mockUseMemoData;
  let mockUseCalendar;
  let user;

  beforeAll(() => {
    dateNowSpy = jest.spyOn(Date, 'now').mockImplementation(() => MOCK_DATE_NOW);
  });

  afterAll(() => {
    dateNowSpy.mockRestore();
  });

  beforeEach(() => {
    user = userEvent.setup();
    const today = moment(MOCK_DATE_NOW);
    const tomorrow = moment(MOCK_DATE_NOW).add(1, 'day');
    mockMemos = [
      { id: 1, title: 'Test Memo 1', content: 'Content 1', reminder_time: today.toISOString(), is_completed: false },
      { id: 2, title: 'Test Memo 2', content: 'Content 2', reminder_time: tomorrow.toISOString(), is_completed: true },
    ];

    mockUseMemoData = {
      memos: mockMemos,
      isLoading: false,
      createMemo: jest.fn(),
      updateMemo: jest.fn(),
      deleteMemo: jest.fn(),
    };

    mockUseCalendar = {
      selectedDate: moment(MOCK_DATE_NOW),
      handleSelectDate: jest.fn(),
    };

    useMemoData.mockReturnValue(mockUseMemoData);
    useCalendar.mockReturnValue(mockUseCalendar);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders loading state initially', () => {
    useMemoData.mockReturnValue({ ...mockUseMemoData, isLoading: true, memos: [] });
    render(<Router><MemoPage /></Router>);
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });

  test('renders memo page with memos for the selected date', () => {
    render(<Router><MemoPage /></Router>);
    expect(screen.getByText('我的备忘录')).toBeInTheDocument();
    
    const allMemosCard = screen.getByTestId('all-memos-card');
    expect(within(allMemosCard).getByText('Test Memo 1')).toBeInTheDocument();

    const selectedDateMemosCard = screen.getByTestId('selected-date-memos-card');
    expect(within(selectedDateMemosCard).getByText('Test Memo 1')).toBeInTheDocument();
  });

  test('opens and closes create memo modal', async () => {
    render(<Router><MemoPage /></Router>);
    await user.click(screen.getByRole('button', { name: /新建备忘录/i }));
    const modal = await screen.findByRole('dialog', { name: /新建备忘录/i });
    expect(modal).toBeInTheDocument();

    await user.click(within(modal).getByRole('button', { name: /取 消/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: /新建备忘录/i })).not.toBeInTheDocument();
    });
  });

  test('opens and closes edit memo modal', async () => {
    render(<Router><MemoPage /></Router>);
    const editButtons = await screen.findAllByLabelText('edit');
    await user.click(editButtons[0]);
    
    const modal = await screen.findByRole('dialog', { name: /编辑备忘录/i });
    expect(modal).toBeInTheDocument();

    await user.click(within(modal).getByRole('button', { name: /取 消/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: /编辑备忘录/i })).not.toBeInTheDocument();
    });
  });

  test('calls deleteMemo when delete confirmation is accepted', async () => {
    render(<Router><MemoPage /></Router>);
    const deleteButtons = await screen.findAllByLabelText('delete');
    await user.click(deleteButtons[0]);

    const confirmButton = await screen.findByRole('button', { name: '是' });
    await user.click(confirmButton);

    await waitFor(() => expect(mockUseMemoData.deleteMemo).toHaveBeenCalledWith(1, expect.any(Object)));
  });

  test('calls updateMemo when checkbox is toggled', async () => {
    render(<Router><MemoPage /></Router>);
    const checkboxes = await screen.findAllByRole('checkbox');
    await user.click(checkboxes[0]);
    expect(mockUseMemoData.updateMemo).toHaveBeenCalledWith({ id: 1, data: { is_completed: true } }, expect.any(Object));
  });

  test('filters memos when a different date is selected', async () => {
    const { rerender } = render(<Router><MemoPage /></Router>);
    const selectedDateCard1 = screen.getByTestId('selected-date-memos-card');
    expect(within(selectedDateCard1).getByText('Test Memo 1')).toBeInTheDocument();
    expect(within(selectedDateCard1).queryByText('Test Memo 2')).not.toBeInTheDocument();

    const nextDay = moment(MOCK_DATE_NOW).add(1, 'day');
    
    useCalendar.mockReturnValue({
      ...mockUseCalendar,
      selectedDate: nextDay,
    });
    
    rerender(<Router><MemoPage /></Router>);

    await waitFor(() => {
      const selectedDateCard2 = screen.getByTestId('selected-date-memos-card');
      expect(screen.getByText(`选定日期备忘录 (${nextDay.format('YYYY年MM月DD日')})`)).toBeInTheDocument();
      expect(within(selectedDateCard2).getByText('Test Memo 2')).toBeInTheDocument();
      expect(within(selectedDateCard2).queryByText('Test Memo 1')).not.toBeInTheDocument();
    }, { timeout: 2000 });
  });
});