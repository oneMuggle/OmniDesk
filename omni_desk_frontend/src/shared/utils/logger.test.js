import { logger } from './logger';

describe('logger', () => {
  const originalInfo = console.info;
  const originalWarn = console.warn;
  const originalError = console.error;

  beforeEach(() => {
    console.info = jest.fn();
    console.warn = jest.fn();
    console.error = jest.fn();
  });

  afterEach(() => {
    console.info = originalInfo;
    console.warn = originalWarn;
    console.error = originalError;
  });

  it('should log info with prefix', () => {
    logger.info('test message');
    expect(console.info).toHaveBeenCalledWith('[OmniDesk]', 'test message');
  });

  it('should log warn with prefix', () => {
    logger.warn('warning message');
    expect(console.warn).toHaveBeenCalledWith('[OmniDesk]', 'warning message');
  });

  it('should log error with prefix', () => {
    logger.error('error message');
    expect(console.error).toHaveBeenCalledWith('[OmniDesk]', 'error message');
  });

  it('should log multiple arguments', () => {
    logger.info('msg', { data: 1 });
    expect(console.info).toHaveBeenCalledWith('[OmniDesk]', 'msg', { data: 1 });
  });
});
