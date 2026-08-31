import apiClient from './apiClient';
import {
  clearAuthTokens,
  readAuthTokens,
  writeAuthTokens,
} from '../utils/authTokens';

let refreshPromise = null;

function buildRefreshUrl() {
  return `${apiClient.defaults.baseURL}auth/token/refresh/`;
}

function getRequestUrl(input) {
  if (typeof input === 'string') return input;
  if (input instanceof URL) return input.href;
  if (typeof Request !== 'undefined' && input instanceof Request) return input.url;
  return '';
}

function isExternalRequest(input) {
  const url = getRequestUrl(input).trim();
  if (!url || (!url.startsWith('//') && !/^[a-z][a-z\d+.-]*:\/\//i.test(url))) {
    return false;
  }

  const apiOrigin = new URL(apiClient.defaults.baseURL, window.location.origin).origin;
  return new URL(url, window.location.origin).origin !== apiOrigin;
}

function mergeHeaders(headers, token) {
  const merged = new Headers(headers || undefined);
  if (token) {
    merged.set('Authorization', `Bearer ${token}`);
  } else {
    merged.delete('Authorization');
  }
  return merged;
}

function canRetry(init) {
  const body = init.body;
  return !body || typeof body !== 'object' || typeof body.getReader !== 'function';
}

async function refreshAccessToken(signal) {
  const tokens = readAuthTokens();
  if (!tokens?.refresh) return null;

  let response;
  try {
    response = await fetch(buildRefreshUrl(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: tokens.refresh }),
      signal,
    });
  } catch (error) {
    clearAuthTokens();
    throw error;
  }

  if (!response.ok) {
    clearAuthTokens();
    return null;
  }

  let data;
  try {
    data = await response.json();
  } catch {
    clearAuthTokens();
    return null;
  }

  if (typeof data?.access !== 'string' || data.access.length === 0) {
    clearAuthTokens();
    return null;
  }

  const hasRefresh = Object.prototype.hasOwnProperty.call(data, 'refresh');
  if (hasRefresh && (typeof data.refresh !== 'string' || data.refresh.length === 0)) {
    clearAuthTokens();
    return null;
  }

  const nextTokens = {
    access: data.access,
    refresh: hasRefresh ? data.refresh : tokens.refresh,
  };

  if (!writeAuthTokens(nextTokens, tokens.storage)) {
    clearAuthTokens();
    return null;
  }

  return nextTokens.access;
}

function getRefreshedAccessToken(signal) {
  if (!refreshPromise) {
    refreshPromise = refreshAccessToken(signal).finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export async function authFetch(input, init = {}) {
  const tokens = readAuthTokens();
  const isExternal = isExternalRequest(input);
  if (!isExternal && !tokens?.access) {
    throw new Error('AUTH_ERROR');
  }

  const headers = mergeHeaders(init.headers, isExternal ? null : tokens.access);
  const response = await fetch(input, { ...init, headers });

  if (isExternal || response.status !== 401 || !canRetry(init)) return response;

  const nextAccessToken = await getRefreshedAccessToken(init.signal);
  if (!nextAccessToken) return response;

  const retryHeaders = mergeHeaders(init.headers, nextAccessToken);
  return fetch(input, { ...init, headers: retryHeaders });
}

export function resetAuthFetchState() {
  refreshPromise = null;
}
