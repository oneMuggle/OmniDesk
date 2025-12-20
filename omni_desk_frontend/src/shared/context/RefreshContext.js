import React, { createContext, useState, useCallback } from 'react';
import PropTypes from 'prop-types';

export const RefreshContext = createContext();

export const RefreshProvider = ({ children }) => {
  const [refreshKey, setRefreshKey] = useState(0);

  const triggerRefresh = useCallback(() => {
    setRefreshKey(prevKey => prevKey + 1);
  }, []);

  return (
    <RefreshContext.Provider value={{ refreshKey, triggerRefresh }}>
      {children}
    </RefreshContext.Provider>
  );
};

RefreshProvider.propTypes = {
  children: PropTypes.node.isRequired,
};