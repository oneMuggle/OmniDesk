import React, { createContext, useContext, useState, useEffect } from 'react';

export const ApiContext = createContext();

export function ApiProvider({ children }) {
  const [apiConfig, setApiConfig] = useState(() => {
    // 从localStorage加载初始配置
    const savedConfig = localStorage.getItem('apiConfig');
    return savedConfig ? JSON.parse(savedConfig) : {
      apiKey: '',
      apiEndpoint: 'https://api.deepseek.com/v1',
      model: 'deepseek-chat'
    };
  });

  // 持久化配置到localStorage
  useEffect(() => {
    localStorage.setItem('apiConfig', JSON.stringify(apiConfig));
  }, [apiConfig]);

  const value = {
    apiConfig,
    setApiConfig: (newConfig) => {
      setApiConfig(prev => ({ ...prev, ...newConfig }));
    }
  };

  return (
    <ApiContext.Provider value={value}>
      {children}
    </ApiContext.Provider>
  );
}

export function useApi() {
  return useContext(ApiContext);
}
