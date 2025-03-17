import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';
import { getModels } from '../api/ollama';

export const ApiContext = createContext();

export function ApiProvider({ children }) {
  const [apiType, setApiType] = useState(() => {
    const savedType = localStorage.getItem('apiType');
    return savedType || 'deepseek';
  });

  const [apiConfig, setApiConfig] = useState(() => {
    const savedConfig = localStorage.getItem('apiConfig');
    const defaultConfig = {
      deepseek: {
        apiKey: process.env.REACT_APP_DEEPSEEK_API_KEY || '',
        apiEndpoint: process.env.REACT_APP_DEEPSEEK_ENDPOINT || 'https://api.deepseek.com/v1',
        model: 'deepseek-chat'
      },
      ollama: {
        apiEndpoint: process.env.REACT_APP_OLLAMA_ENDPOINT || 'http://localhost:11434/api',
        model: process.env.REACT_APP_OLLAMA_MODEL || 'llama2'
      }
    };
    return savedConfig ? JSON.parse(savedConfig) : defaultConfig[apiType];
  });

  // 持久化配置到localStorage
  useEffect(() => {
    localStorage.setItem('apiConfig', JSON.stringify(apiConfig));
    localStorage.setItem('apiType', apiType);
    // 同步配置到deepseek模块
    import('../api/deepseek').then(({ setApiProvider }) => {
      setApiProvider(apiConfig);
    });
  }, [apiConfig, apiType]);

  const value = {
    apiType,
    apiConfig,
    setApiType: (type) => {
      setApiType(type);
      setApiConfig(prev => ({
        ...prev,
        ...(type === 'ollama' ? { 
          apiEndpoint: process.env.REACT_APP_OLLAMA_ENDPOINT || 'http://localhost:11434/api',
          model: process.env.REACT_APP_OLLAMA_MODEL || 'llama2'
        } : {
          apiKey: process.env.REACT_APP_DEEPSEEK_API_KEY || '',
          apiEndpoint: process.env.REACT_APP_DEEPSEEK_ENDPOINT || 'https://api.deepseek.com/v1',
          model: 'deepseek-chat'
        })
      }));
    },
    setApiConfig: (newConfig) => {
      setApiConfig(prev => ({ ...prev, ...newConfig }));
    },
    getModels
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
