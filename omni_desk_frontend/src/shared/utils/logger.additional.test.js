import { logger } from './logger';

describe('logger additional', () => {
  it('should export logger', () => {
    expect(logger).toBeDefined();
    expect(typeof logger.error).toBe('function');
    expect(typeof logger.warn).toBe('function');
  });
});
