import React, { useState, useContext } from 'react';
import { useApi } from '../context/ApiProvider';
import { setApiProvider } from '../api/deepseek';

function SettingsPage() {
  const { apiConfig, setApiConfig } = useApi();
  const [formData, setFormData] = useState(apiConfig);

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
          <label>API 密钥:</label>
          <input
            type="password"
            name="apiKey"
            value={formData.apiKey}
            onChange={handleChange}
          />
        </div>
        <div className="form-group">
          <label>API 端点:</label>
          <input
            type="url"
            name="apiEndpoint"
            value={formData.apiEndpoint}
            onChange={handleChange}
          />
        </div>
        <div className="form-group">
          <label>模型名称:</label>
          <input
            type="text"
            name="model"
            value={formData.model}
            onChange={handleChange}
          />
        </div>
        <button type="submit">保存配置</button>
      </form>
    </div>
  );
}

export default SettingsPage;
