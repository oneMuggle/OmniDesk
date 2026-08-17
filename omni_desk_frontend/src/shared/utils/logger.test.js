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

describe('logger.sanitizeReport', () => {
  it('should drop keys outside whitelist', () => {
    const out = logger.sanitizeReport({
      kind: 'test',
      message: 'hi',
      password: 'leaked',
      token: 'leaked',
    });
    expect(out).toEqual({ kind: 'test', message: 'hi' });
  });

  it('should recursively strip sensitive keys in extra', () => {
    const out = logger.sanitizeReport({
      kind: 'test',
      extra: {
        username: 'alice',
        password: 'leaked',
        refresh_token: 'leaked',
        apiKey: 'leaked',
        sessionId: 'leaked',
      },
    });
    expect(out.extra).toEqual({ username: 'alice' });
  });

  it('should scrub sensitive query params from url', () => {
    const out = logger.sanitizeReport({
      kind: 'test',
      url: 'https://example.com/oauth?access_token=abc&refresh_token=def&code=xyz&token=tok&keep=1',
    });
    expect(out.url).toBe(
      'https://example.com/oauth?access_token=<redacted>&refresh_token=<redacted>&code=<redacted>&token=<redacted>&keep=1'
    );
  });

  it('should truncate long strings', () => {
    const out = logger.sanitizeReport({
      kind: 'test',
      message: 'x'.repeat(1000),
      stack: 'y'.repeat(10000),
    });
    expect(out.message.length).toBe(500);
    expect(out.stack.length).toBe(5000);
  });

  it('should return empty object for null/undefined input', () => {
    expect(logger.sanitizeReport(null)).toEqual({});
    expect(logger.sanitizeReport(undefined)).toEqual({});
    expect(logger.sanitizeReport('string')).toEqual({});
  });
});

describe('logger.report', () => {
  let originalSendBeacon;
  let originalFetch;

  beforeEach(() => {
    originalSendBeacon = navigator.sendBeacon;
    originalFetch = globalThis.fetch;
    navigator.sendBeacon = jest.fn().mockReturnValue(true);
    globalThis.fetch = jest.fn().mockResolvedValue({ ok: true });
  });

  afterEach(() => {
    navigator.sendBeacon = originalSendBeacon;
    globalThis.fetch = originalFetch;
  });

  it('should call navigator.sendBeacon with sanitized payload', () => {
    logger.report({
      kind: 'test',
      message: 'boom',
      password: 'leaked',
    });
    expect(navigator.sendBeacon).toHaveBeenCalledTimes(1);
    const [url, blob] = navigator.sendBeacon.mock.calls[0];
    expect(url).toMatch(/\/api\/system\/client-error\/$/);
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.type).toBe('application/json');
  });

  it('should not throw when navigator is unavailable', () => {
    const tmp = navigator.sendBeacon;
    delete navigator.sendBeacon;
    delete globalThis.fetch;
    expect(() => logger.report({ kind: 'test' })).not.toThrow();
    navigator.sendBeacon = tmp;
  });
});
