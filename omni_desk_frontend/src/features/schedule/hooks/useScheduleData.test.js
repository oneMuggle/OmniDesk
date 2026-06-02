import { renderHook } from '@testing-library/react';

describe('useScheduleData', () => {
  it('should be importable', async () => {
    const { useScheduleData } = await import('./useScheduleData');
    expect(typeof useScheduleData).toBe('function');
  });
});
