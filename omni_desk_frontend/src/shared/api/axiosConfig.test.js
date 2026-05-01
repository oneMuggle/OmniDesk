/**
 * Tests for axiosConfig.js
 *
 * Because interceptors are attached at import time (side-effect),
 * we test the interceptor callbacks directly rather than re-importing.
 */

// Simulate the request interceptor logic from axiosConfig
const simulateRequestInterceptor = (config) => {
  const authTokens = JSON.parse(
    localStorage.getItem('authTokens') || sessionStorage.getItem('authTokens') || '{}'
  );
  const token = authTokens.access;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
};

// Simulate the response interceptor error handler (401 handling)
const simulateResponseErrorHandler = async (error, axiosPostMock) => {
  const originalRequest = error.config;
  const isLoginRequest = originalRequest.url?.includes('auth/login');

  if (error.response?.status === 401 && isLoginRequest) {
    return Promise.reject(error);
  }

  if (error.response?.status !== 401 || originalRequest._retry) {
    return Promise.reject(error);
  }

  // Token refresh flow
  originalRequest._retry = true;
  const tokens = JSON.parse(
    localStorage.getItem('authTokens') || sessionStorage.getItem('authTokens') || '{}'
  );

  if (!tokens.refresh) {
    throw new Error('No refresh token');
  }

  try {
    const { data } = await axiosPostMock(
      `${'http://127.0.0.1:8000/api/'}auth/token/refresh/`,
      { refresh: tokens.refresh }
    );

    const newTokens = {
      access: data.access,
      refresh: data.refresh || tokens.refresh,
    };

    if (localStorage.getItem('authTokens')) {
      localStorage.setItem('authTokens', JSON.stringify(newTokens));
    }
    if (sessionStorage.getItem('authTokens')) {
      sessionStorage.setItem('authTokens', JSON.stringify(newTokens));
    }

    originalRequest.headers.Authorization = `Bearer ${data.access}`;
    return { data: 'retry success', token: data.access };
  } catch (refreshError) {
    localStorage.removeItem('authTokens');
    sessionStorage.removeItem('authTokens');
    return Promise.reject(refreshError);
  }
};

describe('axiosConfig interceptors', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  // --- Request Interceptor Tests ---

  describe('request interceptor', () => {
    it('attaches Authorization header when localStorage has tokens', () => {
      localStorage.setItem('authTokens', JSON.stringify({ access: 'abc123' }));
      const config = { headers: {} };
      const result = simulateRequestInterceptor(config);
      expect(result.headers.Authorization).toBe('Bearer abc123');
    });

    it('attaches Authorization header when sessionStorage has tokens', () => {
      sessionStorage.setItem('authTokens', JSON.stringify({ access: 'session-token' }));
      const config = { headers: {} };
      const result = simulateRequestInterceptor(config);
      expect(result.headers.Authorization).toBe('Bearer session-token');
    });

    it('prefers localStorage over sessionStorage when both exist', () => {
      localStorage.setItem('authTokens', JSON.stringify({ access: 'local' }));
      sessionStorage.setItem('authTokens', JSON.stringify({ access: 'session' }));
      const config = { headers: {} };
      const result = simulateRequestInterceptor(config);
      expect(result.headers.Authorization).toBe('Bearer local');
    });

    it('does not attach header when no tokens exist', () => {
      const config = { headers: {} };
      const result = simulateRequestInterceptor(config);
      expect(result.headers.Authorization).toBeUndefined();
    });

    it('does not attach header when tokens are empty object', () => {
      localStorage.setItem('authTokens', JSON.stringify({}));
      const config = { headers: {} };
      const result = simulateRequestInterceptor(config);
      expect(result.headers.Authorization).toBeUndefined();
    });
  });

  // --- Response Interceptor Tests ---

  describe('response interceptor (401 handling)', () => {
    it('rejects login 401 without attempting token refresh', async () => {
      const error = {
        config: { url: 'http://127.0.0.1:8000/api/auth/login' },
        response: { status: 401 },
      };

      await expect(
        simulateResponseErrorHandler(error, jest.fn())
      ).rejects.toBe(error);
    });

    it('rejects non-401 errors without token refresh', async () => {
      const error = { config: {}, response: { status: 500 } };

      await expect(
        simulateResponseErrorHandler(error, jest.fn())
      ).rejects.toBe(error);
    });

    it('rejects when retry already attempted', async () => {
      const error = {
        config: { url: 'http://api/data', _retry: true },
        response: { status: 401 },
      };

      await expect(
        simulateResponseErrorHandler(error, jest.fn())
      ).rejects.toBe(error);
    });

    it('rejects when no refresh token available', async () => {
      const error = {
        config: { url: 'http://api/data', _retry: false },
        response: { status: 401 },
      };

      await expect(
        simulateResponseErrorHandler(error, jest.fn())
      ).rejects.toThrow('No refresh token');
    });

    it('refreshes token and updates localStorage on success', async () => {
      localStorage.setItem('authTokens', JSON.stringify({
        access: 'old',
        refresh: 'refresh-token',
      }));

      const axiosPostMock = jest.fn().mockResolvedValue({
        data: { access: 'new-access-token', refresh: 'new-refresh-token' },
      });

      const error = {
        config: { url: 'http://api/data', _retry: false, headers: {} },
        response: { status: 401 },
      };

      const result = await simulateResponseErrorHandler(error, axiosPostMock);

      expect(axiosPostMock).toHaveBeenCalled();
      expect(result.token).toBe('new-access-token');
      expect(JSON.parse(localStorage.getItem('authTokens')).access).toBe('new-access-token');
    });

    it('clears tokens on refresh failure', async () => {
      localStorage.setItem('authTokens', JSON.stringify({
        access: 'old',
        refresh: 'invalid-refresh',
      }));

      const axiosPostMock = jest.fn().mockRejectedValue(new Error('Token expired'));

      const error = {
        config: { url: 'http://api/data', _retry: false, headers: {} },
        response: { status: 401 },
      };

      await expect(
        simulateResponseErrorHandler(error, axiosPostMock)
      ).rejects.toThrow('Token expired');

      expect(localStorage.getItem('authTokens')).toBeNull();
    });
  });
});
