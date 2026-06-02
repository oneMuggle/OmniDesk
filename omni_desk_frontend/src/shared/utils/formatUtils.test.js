describe('formatUtils', () => {
  it('should be importable', async () => {
    const utils = await import('./formatUtils');
    expect(typeof utils).toBe('object');
  });
});
