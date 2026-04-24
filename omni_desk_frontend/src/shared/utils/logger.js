const isDev = process.env.NODE_ENV === 'development';

export const logger = {
  debug: (...args) => isDev && console.debug('[OmniDesk]', ...args),
  info: (...args) => console.info('[OmniDesk]', ...args),
  warn: (...args) => console.warn('[OmniDesk]', ...args),
  error: (...args) => console.error('[OmniDesk]', ...args),
};
