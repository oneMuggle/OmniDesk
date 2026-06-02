describe('scheduleUtils', () => {
  it('should be importable', async () => {
    const utils = await import('./scheduleUtils');
    expect(typeof utils).toBe('object');
  });
});
