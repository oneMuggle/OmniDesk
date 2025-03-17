import React, { useState, useEffect } from 'react';
import { useApi } from '../context/ApiProvider';
import { setApiProvider } from '../api/deepseek';

function SettingsPage() {
  const { apiConfig, setApiConfig, getModels } = useApi();
  const [formData, setFormData] = useState(apiConfig);
  const [apiType, setApiType] = useState(apiConfig.apiType || 'deepseek');
  const [models, setModels] = useState([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [modelError, setModelError] = useState('');

  useEffect(() => {
    const fetchModels = async () => {
      if (apiType === 'ollama') {
        setIsLoadingModels(true);
        setModelError('');
        try {
          const modelList = await getModels();
          setModels(modelList);
        } catch (error) {
          setModelError('无法加载模型列表，请检查服务器连接');
          console.error(error);
        } finally {
          setIsLoadingModels(false);
        }
      }
    };

    fetchModels();
  }, [apiType, getModels]);

  const handleSubmit = (e) => {
    e.preventDefault();
    setApiConfig(formData);
    setApiProvider(formData); // 更新API客户端配置
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  return (
    <div className="settings-container">
      <h2>API 配置</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>API 提供商:</label>
          <select
            name="apiType"
            value={apiType}
            onChange={(e) => {
              setApiType(e.target.value);
              handleChange(e);
            }}
          >
            <option value="deepseek">DeepSeek</option>
            <option value="ollama">Ollama</option>
          </select>
        </div>

        {apiType === 'deepseek' && (
          <div className="form-group">
            <label>API 密钥:</label>
            <input
              type="password"
              name="apiKey"
              value={formData.apiKey || ''}
              onChange={handleChange}
            />
          </div>
        )}

        <div className="form-group">
          <label>{apiType === 'ollama' ? '服务器地址' : 'API 端点'}:</label>
          <input
            type="url"
            name="apiEndpoint"
            value={formData.apiEndpoint}
            onChange={handleChange}
          />
        </div>
        {apiType === 'deepseek' ? (
          <div className="form-group">
            <label>模型名称:</label>
            <input
              type="text"
              name="model"
              value={formData.model}
              onChange={handleChange}
            />
          </div>
        ) : (
          <div className="form-group">
            <label>选择模型:</label>
            {isLoadingModels ? (
              <div>正在加载可用模型...</div>
            ) : modelError ? (
              <div className="error-message">{modelError}</div>
            ) : (
              <select
                name="model"
                value={formData.model}
                onChange={handleChange}
                disabled={models.length === 0}
              >
                {models.map(model => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            )}
          </div>
        )}
        <button type="submit">保存配置</button>
      </form>
    </div>
  );
}

export default SettingsPage;
