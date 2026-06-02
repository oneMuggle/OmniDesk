import apiClient from './apiClient';

describe('apiClient', () => {
  it('should export axios instance', () => {
    expect(apiClient).toBeDefined();
    expect(typeof apiClient.get).toBe('function');
    expect(typeof apiClient.post).toBe('function');
  });
});
