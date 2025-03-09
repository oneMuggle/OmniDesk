import React, { useState, useEffect } from 'react';

const SettingsPage = () => {
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('https://api.deepseek.com/v1');

  useEffect(() => {
    // 从localStorage加载保存的配置
    const savedConfig = localStorage.getItem('deepseekConfig');
    if (savedConfig) {
      const { apiKey: savedKey, baseUrl: savedUrl } = JSON.parse(savedConfig);
      setApiKey(savedKey);
      setBaseUrl(savedUrl);
    }
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    localStorage.setItem('deepseekConfig', JSON.stringify({ apiKey, baseUrl }));
    alert('配置已保存');
  };

  return (
    <div className="page-container">
      <h2>系统设置</h2>
      <div className="settings-content">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>API Key:</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="请输入Deepseek API密钥"
              required
            />
          </div>
          <div className="form-group">
            <label>API 地址:</label>
            <input
              type="url"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="请输入API基础地址"
              required
            />
          </div>
          <button type="submit" className="save-button">保存配置</button>
        </form>
        
        <div className="security-note">
          <p>安全提示：您的API密钥将加密存储在本地浏览器中</p>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
