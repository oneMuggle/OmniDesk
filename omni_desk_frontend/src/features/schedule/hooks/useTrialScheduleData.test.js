import { renderHook } from '@testing-library/react';

describe('useTrialScheduleData', () => {
  it('should be importable', async () => {
    const { useTrialScheduleData } = await import('./useTrialScheduleData');
    expect(typeof useTrialScheduleData).toBe('function');
  });
});
