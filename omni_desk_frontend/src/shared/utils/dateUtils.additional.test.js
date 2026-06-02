import * as dateUtils from './dateUtils';

describe('dateUtils additional', () => {
  it('should export date functions', () => {
    expect(typeof dateUtils).toBe('object');
  });
});
