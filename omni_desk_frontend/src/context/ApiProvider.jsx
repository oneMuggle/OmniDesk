/* eslint-disable no-undef */
import React, { createContext, useContext, useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { getModels } from '../api/ollama';

export const ApiContext = createContext();

export function ApiProvider({ children }) {
  const [conversationHistory, setConversationHistory] = useState([]);
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
      },
      ragflow: {
        // Ragflow 的配置，例如只需要一个占位符，实际配置从后端获取
        apiEndpoint: '', // 实际的Ragflow API端点将从后端配置中获取
        apiKey: '' // 实际的Ragflow API Key将从后端配置中获取
      },
      dify: {
        // Dify 的配置，例如只需要一个占位符，实际配置从后端获取
        apiEndpoint: '', // 实际的Dify API端点将从后端配置中获取
        apiKey: '' // 实际的Dify API Key将从后端配置中获取
      }
    };
    // 确保从localStorage加载的配置是完整的，如果缺少新API类型，则补充默认值
    const mergedConfig = savedConfig ? { ...defaultConfig, ...JSON.parse(savedConfig) } : defaultConfig;
    return mergedConfig[apiType] ? mergedConfig : { ...mergedConfig, ...defaultConfig[apiType] };
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
    conversationHistory,
    setConversationHistory,
    setApiType: (type) => {
      setApiType(type);
      setApiConfig(prev => {
        const newConfig = { ...prev };
        switch (type) {
          case 'ollama':
            newConfig.ollama = {
              apiEndpoint: process.env.REACT_APP_OLLAMA_ENDPOINT || 'http://localhost:11434/api',
              model: process.env.REACT_APP_OLLAMA_MODEL || 'llama2'
            };
            break;
          case 'deepseek':
            newConfig.deepseek = {
              apiKey: process.env.REACT_APP_DEEPSEEK_API_KEY || '',
              apiEndpoint: process.env.REACT_APP_DEEPSEEK_ENDPOINT || 'https://api.deepseek.com/v1',
              model: 'deepseek-chat'
            };
            break;
          case 'ragflow':
            newConfig.ragflow = {
              apiEndpoint: '', // Ragflow的实际API端点将从后端配置中获取
              apiKey: '' // Ragflow的实际API Key将从后端配置中获取
            };
            break;
          case 'dify':
            newConfig.dify = {
              apiEndpoint: '', // Dify的实际API端点将从后端配置中获取
              apiKey: '' // Dify的实际API Key将从后端配置中获取
            };
            break;
          default:
            break;
        }
        return newConfig;
      });
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

ApiProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

export function useApi() {
  return useContext(ApiContext);
}
