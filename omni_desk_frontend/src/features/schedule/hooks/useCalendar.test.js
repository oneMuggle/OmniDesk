import { renderHook, act } from '@testing-library/react';
import { useCalendar } from './useCalendar';

describe('useCalendar', () => {
  it('should initialize with default date', () => {
    const { result } = renderHook(() => useCalendar());
    expect(result.current.selectedDate).toBeDefined();
  });

  it('should initialize with provided date', () => {
    const mockDate = { format: () => '2024-06-15' };
    const { result } = renderHook(() => useCalendar(mockDate));
    expect(result.current.selectedDate).toBe(mockDate);
  });

  it('should update selected date on handleSelectDate', () => {
    const { result } = renderHook(() => useCalendar());
    const newDate = { format: () => '2024-12-25' };
    act(() => {
      result.current.handleSelectDate(newDate);
    });
    expect(result.current.selectedDate).toBe(newDate);
  });
});
