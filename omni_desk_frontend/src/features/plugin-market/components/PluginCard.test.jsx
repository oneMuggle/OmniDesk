describe('PluginCard', () => {
  it('should be importable', async () => {
    const PluginCard = await import('./PluginCard');
    expect(PluginCard).toBeDefined();
  });
});
