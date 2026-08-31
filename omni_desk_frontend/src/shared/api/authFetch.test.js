import {
  clearAuthTokens,
  readAuthTokens,
  writeAuthTokens,
} from '../utils/authTokens';
import { authFetch, resetAuthFetchState } from './authFetch';

jest.mock('./apiClient', () => ({
  __esModule: true,
  default: { defaults: { baseURL: '/api/' } },
}));

jest.mock('../utils/authTokens', () => ({
  clearAuthTokens: jest.fn(),
  readAuthTokens: jest.fn(),
  writeAuthTokens: jest.fn(),
}));

function response(status, body) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: body === undefined ? jest.fn() : jest.fn().mockResolvedValue(body),
  };
}

function requestHeaders(call) {
  const headers = call[1].headers;
  return headers instanceof Headers
    ? Object.fromEntries(headers.entries())
    : Object.fromEntries(new Headers(headers).entries());
}

describe('authFetch', () => {
  let tokens;

  beforeEach(() => {
    tokens = { access: 'old-access', refresh: 'old-refresh', storage: 'localStorage' };
    readAuthTokens.mockImplementation(() => tokens);
    writeAuthTokens.mockImplementation((nextTokens) => {
      tokens = { ...nextTokens, storage: tokens.storage };
      return true;
    });
    globalThis.fetch = jest.fn();
    clearAuthTokens.mockReset();
    readAuthTokens.mockClear();
    writeAuthTokens.mockClear();
    resetAuthFetchState();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('throws AUTH_ERROR and does not fetch when no access token exists', async () => {
    readAuthTokens.mockReturnValue(null);

    await expect(authFetch('/api/private/')).rejects.toThrow('AUTH_ERROR');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('adds Bearer to internal requests and preserves ordinary headers', async () => {
    fetch.mockResolvedValue(response(200));
    const init = { method: 'GET', headers: { Accept: 'application/json', 'X-Trace': 'abc' } };

    await authFetch('/api/private/', init);

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toBe('/api/private/');
    expect(requestHeaders(fetch.mock.calls[0])).toEqual({
      accept: 'application/json',
      authorization: 'Bearer old-access',
      'x-trace': 'abc',
    });
    expect(init.headers).toEqual({ Accept: 'application/json', 'X-Trace': 'abc' });
  });

  it('adds Bearer to an internal absolute URL based on the configured API base URL', async () => {
    fetch.mockResolvedValue(response(200));

    await authFetch('http://localhost/api/private/');

    expect(requestHeaders(fetch.mock.calls[0])).toMatchObject({
      authorization: 'Bearer old-access',
    });
  });

  it('does not add Bearer or refresh an external absolute URL after 401', async () => {
    fetch.mockResolvedValue(response(401));

    const result = await authFetch('https://external.example/resource');

    expect(result.status).toBe(401);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(requestHeaders(fetch.mock.calls[0])).not.toHaveProperty('authorization');
    expect(writeAuthTokens).not.toHaveBeenCalled();
    expect(clearAuthTokens).not.toHaveBeenCalled();
  });

  it.each([
    ['leading space', ' https://external.example/resource'],
    ['leading tab', '\thttps://external.example/resource'],
    ['leading newline', '\nhttps://external.example/resource'],
  ])(
    'does not add Authorization for an external absolute URL with %s',
    async (_case, input) => {
      fetch.mockResolvedValue(response(200));

      const result = await authFetch(input);

      expect(result.status).toBe(200);
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(requestHeaders(fetch.mock.calls[0])).not.toHaveProperty('authorization');
      expect(writeAuthTokens).not.toHaveBeenCalled();
      expect(clearAuthTokens).not.toHaveBeenCalled();
    }
  );

  it('merges Headers instances and replaces a caller Authorization header', async () => {
    fetch.mockResolvedValue(response(200));
    const headers = new Headers([
      ['Accept', 'application/json'],
      ['Authorization', 'Bearer caller-token'],
      ['X-Trace', 'headers-value'],
    ]);

    await authFetch('/api/private/', { headers });

    expect(requestHeaders(fetch.mock.calls[0])).toEqual({
      accept: 'application/json',
      authorization: 'Bearer old-access',
      'x-trace': 'headers-value',
    });
  });

  it('merges array headers without losing entries', async () => {
    fetch.mockResolvedValue(response(200));

    await authFetch('/api/private/', {
      headers: [
        ['Accept', 'application/json'],
        ['X-Trace', 'array-value'],
      ],
    });

    expect(requestHeaders(fetch.mock.calls[0])).toEqual({
      accept: 'application/json',
      authorization: 'Bearer old-access',
      'x-trace': 'array-value',
    });
  });

  it('refreshes once after 401 and retries once with the new access token', async () => {
    fetch
      .mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(200, { access: 'new-access' }))
      .mockResolvedValueOnce(response(200));

    const result = await authFetch('/api/private/', { headers: { Accept: 'application/json' } });

    expect(result.status).toBe(200);
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(fetch.mock.calls[0][0]).toBe('/api/private/');
    expect(fetch.mock.calls[1][0]).toBe('/api/auth/token/refresh/');
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ refresh: 'old-refresh' });
    expect(fetch.mock.calls[2][0]).toBe('/api/private/');
    expect(requestHeaders(fetch.mock.calls[2])).toMatchObject({
      authorization: 'Bearer new-access',
    });
  });

  it('persists rotated refresh token and retries with refreshed access token', async () => {
    fetch
      .mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(200, { access: 'new-access', refresh: 'new-refresh' }))
      .mockResolvedValueOnce(response(200));

    await authFetch('/api/private/');

    expect(writeAuthTokens).toHaveBeenCalledWith(
      { access: 'new-access', refresh: 'new-refresh' },
      'localStorage'
    );
    expect(requestHeaders(fetch.mock.calls[2])).toMatchObject({
      authorization: 'Bearer new-access',
    });
  });

  it('does not refresh again when the single retry also returns 401', async () => {
    fetch
      .mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(200, { access: 'new-access' }))
      .mockResolvedValueOnce(response(401));

    const result = await authFetch('/api/private/');

    expect(result.status).toBe(401);
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(fetch.mock.calls.filter(([url]) => url === '/api/auth/token/refresh/')).toHaveLength(1);
  });

  it('keeps the old refresh token when refresh response omits rotation', async () => {
    fetch
      .mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(200, { access: 'new-access' }))
      .mockResolvedValueOnce(response(200));

    await authFetch('/api/private/');

    expect(writeAuthTokens).toHaveBeenCalledWith(
      { access: 'new-access', refresh: 'old-refresh' },
      'localStorage'
    );
  });

  it.each([
    ['missing access', {}],
    ['numeric access', { access: 123 }],
    ['empty access', { access: '' }],
    ['numeric refresh', { access: 'new-access', refresh: 123 }],
    ['empty refresh', { access: 'new-access', refresh: '' }],
  ])('clears tokens and does not retry for %s in refresh response', async (_case, body) => {
    fetch
      .mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(200, body));

    const result = await authFetch('/api/private/');

    expect(result.status).toBe(401);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(clearAuthTokens).toHaveBeenCalledTimes(1);
    expect(writeAuthTokens).not.toHaveBeenCalled();
  });

  it('returns the original 401 without refreshing when refresh token is absent', async () => {
    tokens = { access: 'old-access', storage: 'localStorage' };
    fetch.mockResolvedValue(response(401));

    const result = await authFetch('/api/private/');

    expect(result.status).toBe(401);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(clearAuthTokens).not.toHaveBeenCalled();
  });

  it('shares one refresh request among concurrent 401 responses', async () => {
    let releaseRefresh;
    const refreshPending = new Promise((resolve) => {
      releaseRefresh = resolve;
    });
    fetch
      .mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(401))
      .mockReturnValueOnce(refreshPending)
      .mockResolvedValueOnce(response(200))
      .mockResolvedValueOnce(response(200));

    const first = authFetch('/api/one/');
    const second = authFetch('/api/two/');
    await Promise.resolve();
    await Promise.resolve();
    expect(fetch).toHaveBeenCalledTimes(3);

    releaseRefresh(response(200, { access: 'shared-access' }));
    const results = await Promise.all([first, second]);

    expect(results.map(({ status }) => status)).toEqual([200, 200]);
    expect(fetch).toHaveBeenCalledTimes(5);
    expect(fetch.mock.calls.filter(([url]) => url === '/api/auth/token/refresh/')).toHaveLength(1);
    expect(requestHeaders(fetch.mock.calls[3])).toMatchObject({
      authorization: 'Bearer shared-access',
    });
    expect(requestHeaders(fetch.mock.calls[4])).toMatchObject({
      authorization: 'Bearer shared-access',
    });
  });

  it('passes AbortSignal to the initial request, refresh request, and retry', async () => {
    const controller = new AbortController();
    fetch
      .mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(200, { access: 'new-access' }))
      .mockResolvedValueOnce(response(200));

    await authFetch('/api/private/', { signal: controller.signal });

    expect(fetch.mock.calls[0][1].signal).toBe(controller.signal);
    expect(fetch.mock.calls[1][1].signal).toBe(controller.signal);
    expect(fetch.mock.calls[2][1].signal).toBe(controller.signal);
  });
});
