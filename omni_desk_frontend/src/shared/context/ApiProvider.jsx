import { createContext, useContext, useState, useEffect } from 'react';
import PropTypes from 'prop-types';

export const ApiContext = createContext();

export function ApiProvider({ children }) {
  const [conversationHistory, setConversationHistory] = useState([]);

  // 保留旧版 apiType/apiConfig 以兼容 ChatInterface（待迁移后移除）
  const [apiType, setApiTypeState] = useState(() => {
    const savedType = localStorage.getItem('apiType');
    return savedType || 'deepseek';
  });

  const [apiConfig, setApiConfigState] = useState(() => {
    const savedConfig = localStorage.getItem('apiConfig');
    return savedConfig ? JSON.parse(savedConfig) : { deepseek: {} };
  });

  useEffect(() => {
    localStorage.setItem('apiType', apiType);
    localStorage.setItem('apiConfig', JSON.stringify(apiConfig));
  }, [apiType, apiConfig]);

  const value = {
    conversationHistory,
    setConversationHistory,
    apiType,
    apiConfig,
    setApiType: (type) => setApiTypeState(type),
    setApiConfig: (cfg) => setApiConfigState(prev => ({ ...prev, ...cfg })),
    getModels: async () => [], // stub — Ollama models 不再从前端获取
  };

  return (
    <ApiContext.Provider value={value}>
      {children}
    </ApiContext.Provider>
  );
}

ApiProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

export function useApi() {
  return useContext(ApiContext);
}
