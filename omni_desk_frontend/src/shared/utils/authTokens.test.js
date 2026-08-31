import {
  clearAuthTokenStorage,
  clearAuthTokens,
  readAuthTokens,
  writeAuthTokens,
} from './authTokens';

describe('auth token storage', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    jest.restoreAllMocks();
  });

  it('prefers valid localStorage tokens', () => {
    localStorage.setItem('authTokens', JSON.stringify({ access: 'local-access' }));
    sessionStorage.setItem('authTokens', JSON.stringify({ access: 'session-access' }));

    expect(readAuthTokens()).toEqual({
      access: 'local-access',
      refresh: undefined,
      storage: 'localStorage',
    });
  });

  it('clears invalid localStorage and falls back to valid sessionStorage', () => {
    localStorage.setItem('authTokens', '{invalid-json');
    sessionStorage.setItem(
      'authTokens',
      JSON.stringify({ access: 'session-access', refresh: 'session-refresh' })
    );

    expect(readAuthTokens()).toEqual({
      access: 'session-access',
      refresh: 'session-refresh',
      storage: 'sessionStorage',
    });
    expect(localStorage.getItem('authTokens')).toBeNull();
  });

  it.each([
    ['null', null],
    ['an array', []],
    ['an empty object', {}],
    ['a numeric access token', { access: 123 }],
    ['an empty access token', { access: '' }],
    ['a numeric refresh token', { refresh: 123 }],
    ['an empty refresh token', { refresh: '' }],
    ['a mixed valid and invalid token object', { access: 'valid', refresh: null }],
  ])('clears %s and returns null when no valid fallback exists', (_label, value) => {
    localStorage.setItem('authTokens', JSON.stringify(value));

    expect(readAuthTokens()).toBeNull();
    expect(localStorage.getItem('authTokens')).toBeNull();
  });

  it('falls back when localStorage contains invalid data and sessionStorage is also checked', () => {
    localStorage.setItem('authTokens', JSON.stringify({ access: 'local', refresh: 1 }));
    sessionStorage.setItem('authTokens', JSON.stringify({ refresh: 'session-refresh' }));

    expect(readAuthTokens()).toEqual({
      access: undefined,
      refresh: 'session-refresh',
      storage: 'sessionStorage',
    });
    expect(localStorage.getItem('authTokens')).toBeNull();
  });

  it('does not throw when storage APIs are unavailable', () => {
    const originalLocalStorage = window.localStorage;
    const originalSessionStorage = window.sessionStorage;
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get: () => {
        throw new Error('storage unavailable');
      },
    });
    Object.defineProperty(window, 'sessionStorage', {
      configurable: true,
      get: () => {
        throw new Error('storage unavailable');
      },
    });

    expect(() => readAuthTokens()).not.toThrow();
    expect(readAuthTokens()).toBeNull();

    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: originalLocalStorage,
    });
    Object.defineProperty(window, 'sessionStorage', {
      configurable: true,
      value: originalSessionStorage,
    });
  });

  it('writes tokens to the requested storage', () => {
    expect(writeAuthTokens({ access: 'access', refresh: 'refresh' }, 'localStorage')).toBe(true);
    expect(localStorage.getItem('authTokens')).toBe(
      JSON.stringify({ access: 'access', refresh: 'refresh' })
    );
    expect(sessionStorage.getItem('authTokens')).toBeNull();
  });

  it('clears one storage or both storages', () => {
    localStorage.setItem('authTokens', JSON.stringify({ access: 'local' }));
    sessionStorage.setItem('authTokens', JSON.stringify({ access: 'session' }));

    clearAuthTokenStorage('localStorage');
    expect(localStorage.getItem('authTokens')).toBeNull();
    expect(sessionStorage.getItem('authTokens')).not.toBeNull();

    clearAuthTokens();
    expect(sessionStorage.getItem('authTokens')).toBeNull();
  });
});
