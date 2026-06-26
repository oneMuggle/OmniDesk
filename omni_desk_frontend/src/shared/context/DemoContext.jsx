import { createContext, useContext, useState, useCallback } from 'react';
import PropTypes from 'prop-types';

const STORAGE_KEY = 'omnidesk:demo-mode';

const DemoContext = createContext(null);

export function DemoProvider({ children }) {
  const [isDemoMode, setIsDemoMode] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  });

  const setDemoMode = useCallback((value) => {
    setIsDemoMode(value);
    try {
      localStorage.setItem(STORAGE_KEY, String(value));
    } catch {
      // localStorage 不可用，忽略
    }
  }, []);

  const value = {
    isDemoMode,
    setDemoMode,
  };

  return (
    <DemoContext.Provider value={value}>
      {children}
    </DemoContext.Provider>
  );
}

export function useDemoMode() {
  const context = useContext(DemoContext);
  if (!context) {
    throw new Error('useDemoMode must be used within a DemoProvider');
  }
  return context;
}

DemoProvider.propTypes = {
  children: PropTypes.node.isRequired,
};
