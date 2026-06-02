describe('ScheduleControls', () => {
  it('should be importable', async () => {
    const ScheduleControls = await import('./ScheduleControls');
    expect(ScheduleControls).toBeDefined();
  });
});
