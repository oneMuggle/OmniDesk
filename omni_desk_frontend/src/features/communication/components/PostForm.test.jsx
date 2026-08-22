describe('PostForm', () => {
  it('should be importable', async () => {
    const PostForm = await import('./PostForm');
    expect(PostForm).toBeDefined();
  });
});
