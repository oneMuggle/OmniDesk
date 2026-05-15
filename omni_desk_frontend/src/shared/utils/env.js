// Vite-compatible env helper, also works with Jest
// Uses dynamic evaluation to avoid static import.meta syntax that breaks Jest

function getImportMeta() {
  try {
    return new Function('return import.meta')();
  } catch {
    return undefined;
  }
}

const meta = getImportMeta();
const env = meta?.env || Object.fromEntries(
  Object.entries(process.env || {})
    .filter(([key]) => key.startsWith('VITE_') || key.startsWith('REACT_APP_'))
    .map(([key, value]) => [key.replace(/^REACT_APP_/, 'VITE_'), value])
);

export function getEnv(key, defaultValue = '') {
  return env[key] ?? defaultValue;
}

export const isDev = meta?.DEV ?? process.env.NODE_ENV === 'development';
