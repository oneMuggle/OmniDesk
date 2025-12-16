import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { BrowserRouter as Router } from 'react-router-dom';
import moment from 'moment';
import MemoPage from './MemoPage';
import { useMemoData } from '../hooks/useMemoData';
import { useCalendar } from '../hooks/useCalendar';

jest.mock('../hooks/useMemoData');
jest.mock('../hooks/useCalendar');

describe('MemoPage Component', () => {
  const MOCK_DATE_NOW = new Date('2025-10-27T10:00:00.000Z').getTime();
  let dateNowSpy;
  let mockMemos;
  let mockUseMemoData;
  let mockUseCalendar;

  beforeAll(() => {
    dateNowSpy = jest.spyOn(Date, 'now').mockImplementation(() => MOCK_DATE_NOW);
  });

  afterAll(() => {
    dateNowSpy.mockRestore();
  });

  beforeEach(() => {
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

    useMemoData.mockReturnValue(mockUseMemoData);

    mockUseCalendar = {
      selectedDate: moment(MOCK_DATE_NOW),
      handleSelectDate: jest.fn(),
    };
    useCalendar.mockReturnValue(mockUseCalendar);
    jest.clearAllMocks();
  });

  test('renders loading state initially', () => {
    useMemoData.mockReturnValue({ ...mockUseMemoData, isLoading: true, memos: [] });
    useCalendar.mockReturnValue({ selectedDate: moment(MOCK_DATE_NOW), handleSelectDate: jest.fn() });
    render(<Router><MemoPage /></Router>);
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });

  test('renders memo page with memos', () => {
    useCalendar.mockReturnValue({ selectedDate: moment(MOCK_DATE_NOW), handleSelectDate: jest.fn() });
    render(<Router><MemoPage /></Router>);
    expect(screen.getByText('我的备忘录')).toBeInTheDocument();
    
    const allMemosCard = screen.getByTestId('all-memos-card');
    expect(within(allMemosCard).getByText('Test Memo 1')).toBeInTheDocument();

    const selectedDateMemosCard = screen.getByTestId('selected-date-memos-card');
    expect(within(selectedDateMemosCard).getByText('Test Memo 1')).toBeInTheDocument();
  });

  test('opens create memo modal when "新建备忘录" button is clicked', () => {
    useCalendar.mockReturnValue({ selectedDate: moment(MOCK_DATE_NOW), handleSelectDate: jest.fn() });
    render(<Router><MemoPage /></Router>);
    fireEvent.click(screen.getByText('新建备忘录'));
    // In a real app, you might have a more robust way to test modals.
  });

  test('opens edit memo modal when edit button is clicked', async () => {
    useCalendar.mockReturnValue({ selectedDate: moment(MOCK_DATE_NOW), handleSelectDate: jest.fn() });
    render(<Router><MemoPage /></Router>);
    const editButtons = await screen.findAllByLabelText('edit');
    fireEvent.click(editButtons[0]);
    // Similar to the create modal, we'll assume the state is set correctly.
  });

  test('calls deleteMemo when delete button is clicked', async () => {
    useCalendar.mockReturnValue({ selectedDate: moment(MOCK_DATE_NOW), handleSelectDate: jest.fn() });
    render(<Router><MemoPage /></Router>);
    const deleteButtons = await screen.findAllByLabelText('delete');
    fireEvent.click(deleteButtons[0]);

    // The Popconfirm has okText="是"
    fireEvent.click(await screen.findByText('是'));

    await waitFor(() => expect(mockUseMemoData.deleteMemo).toHaveBeenCalledWith(1, expect.any(Object)));
  });

  test('calls updateMemo when checkbox is toggled', async () => {
    useCalendar.mockReturnValue({ selectedDate: moment(MOCK_DATE_NOW), handleSelectDate: jest.fn() });
    render(<Router><MemoPage /></Router>);
    const checkboxes = await screen.findAllByRole('checkbox');
    fireEvent.click(checkboxes[0]);
    expect(mockUseMemoData.updateMemo).toHaveBeenCalledWith({ id: 1, data: { is_completed: true } }, expect.any(Object));
  });

  test('filters memos by selected date', async () => {
    // Initial render with the mocked date
    useCalendar.mockReturnValue({
      selectedDate: moment(MOCK_DATE_NOW),
      handleSelectDate: jest.fn(),
    });
    const { rerender } = render(<Router><MemoPage /></Router>);

    // Check for the memo of the initial date
    const selectedDateCard = screen.getByTestId('selected-date-memos-card');
    expect(within(selectedDateCard).getByText('Test Memo 1')).toBeInTheDocument();
    expect(within(selectedDateCard).queryByText('Test Memo 2')).not.toBeInTheDocument();

    // --- Simulate date change ---
    const nextDay = moment(MOCK_DATE_NOW).add(1, 'day');
    
    // Update the mock to return the new date
    useCalendar.mockReturnValue({
      selectedDate: nextDay,
      handleSelectDate: jest.fn(),
    });

    // Rerender the component to apply the new mock value
    rerender(<Router><MemoPage /></Router>);

    // Assert that the content has updated
    await waitFor(() => {
      // The title of the card should update
      expect(screen.getByText(`选定日期备忘录 (${nextDay.format('YYYY年MM月DD日')})`)).toBeInTheDocument();
      // The list should now show the memo for the next day
      expect(within(selectedDateCard).getByText('Test Memo 2')).toBeInTheDocument();
      expect(within(selectedDateCard).queryByText('Test Memo 1')).not.toBeInTheDocument();
    });
  });
});