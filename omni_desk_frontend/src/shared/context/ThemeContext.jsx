import { createContext, useContext, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { DEFAULT_THEME, getSchemeById, THEME_OPTIONS } from '../theme/themeSchemes';

const STORAGE_KEY = 'preferred-theme';
const DATA_ATTR = 'data-theme';

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [currentTheme, setCurrentTheme] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && THEME_OPTIONS.find(t => t.id === saved)) return saved;
    } catch { /* ignore */ }
    return DEFAULT_THEME;
  });

  useEffect(() => {
    document.documentElement.setAttribute(DATA_ATTR, currentTheme);
  }, [currentTheme]);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, currentTheme);
    } catch { /* ignore */ }
  }, [currentTheme]);

  const setTheme = (themeId) => {
    if (THEME_OPTIONS.find(t => t.id === themeId)) {
      setCurrentTheme(themeId);
    }
  };

  const scheme = getSchemeById(currentTheme);

  const value = {
    currentTheme,
    themeId: currentTheme,
    scheme,
    setTheme,
    themeOptions: THEME_OPTIONS,
  };

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}

ThemeProvider.propTypes = {
  children: PropTypes.node.isRequired,
};
