const AUTH_TOKENS_KEY = 'authTokens';

function getStorage(storageName) {
  try {
    return window[storageName];
  } catch {
    return null;
  }
}

function removeStoredTokens(storage) {
  if (!storage) return;

  try {
    storage.removeItem(AUTH_TOKENS_KEY);
  } catch {
    // Storage may be unavailable in privacy-restricted browsers.
  }
}

function parseStoredTokens(storage) {
  if (!storage) return null;

  let raw;
  try {
    raw = storage.getItem(AUTH_TOKENS_KEY);
  } catch {
    return null;
  }

  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('Invalid auth token structure');
    }

    const hasAccess = typeof parsed.access === 'string' && parsed.access.length > 0;
    const hasRefresh = typeof parsed.refresh === 'string' && parsed.refresh.length > 0;
    const hasInvalidAccess = parsed.access !== undefined && !hasAccess;
    const hasInvalidRefresh = parsed.refresh !== undefined && !hasRefresh;

    if ((!hasAccess && !hasRefresh) || hasInvalidAccess || hasInvalidRefresh) {
      throw new Error('Invalid auth token values');
    }

    return {
      access: hasAccess ? parsed.access : undefined,
      refresh: hasRefresh ? parsed.refresh : undefined,
    };
  } catch {
    removeStoredTokens(storage);
    return null;
  }
}

export function readAuthTokens() {
  const local = parseStoredTokens(getStorage('localStorage'));
  if (local) return { ...local, storage: 'localStorage' };

  const session = parseStoredTokens(getStorage('sessionStorage'));
  if (session) return { ...session, storage: 'sessionStorage' };

  return null;
}

export function writeAuthTokens(tokens, storageName = 'sessionStorage') {
  const storage = getStorage(storageName);
  if (!storage) return false;

  try {
    storage.setItem(AUTH_TOKENS_KEY, JSON.stringify(tokens));
    return true;
  } catch {
    return false;
  }
}

export function clearAuthTokens() {
  removeStoredTokens(getStorage('localStorage'));
  removeStoredTokens(getStorage('sessionStorage'));
}

export function clearAuthTokenStorage(storageName) {
  removeStoredTokens(getStorage(storageName));
}

export { AUTH_TOKENS_KEY };
