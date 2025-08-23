import React, { useState, useEffect } from 'react';
import { getOllamaConfigs, addOllamaConfig, updateOllamaConfig, deleteOllamaConfig, getOllamaModelsFromEndpoint } from '../api/ollama';

const SettingsPage = () => {
  const [configs, setConfigs] = useState([]);
  const [editingConfig, setEditingConfig] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);

  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    const response = await getOllamaConfigs();
    setConfigs(response.data);
  };

  const handleEdit = (config) => {
    setEditingConfig({ ...config });
  };

  const handleDelete = async (id) => {
    await deleteOllamaConfig(id);
    loadConfigs();
  };

  const handleSave = async () => {
    if (editingConfig.id) {
      await updateOllamaConfig(editingConfig.id, editingConfig);
    } else {
      await addOllamaConfig(editingConfig);
    }
    setEditingConfig(null);
    loadConfigs();
  };

  const handleAddNew = () => {
    setEditingConfig({
      alias: '',
      api_endpoint: '',
      model: '',
      temperature: 0.8,
      top_p: 0.9,
      is_default: false,
    });
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setEditingConfig({
      ...editingConfig,
      [name]: type === 'checkbox' ? checked : value,
    });
  };

  const handleFetchModels = async () => {
    if (editingConfig && editingConfig.api_endpoint) {
      try {
        const response = await getOllamaModelsFromEndpoint(editingConfig.api_endpoint);
        setAvailableModels(response.data);
      } catch (error) {
        console.error("Failed to fetch models:", error);
        alert("获取模型列表失败，请检查 API 地址是否正确。");
      }
    }
  };

  return (
    <div>
      <h1>Ollama 配置</h1>
      <button onClick={handleAddNew}>添加新的配置</button>
      <table>
        <thead>
          <tr>
            <th>别名</th>
            <th>API 地址</th>
            <th>模型</th>
            <th>默认</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {configs.map((config) => (
            <tr key={config.id}>
              <td>{config.alias}</td>
              <td>{config.api_endpoint}</td>
              <td>{config.model}</td>
              <td>{config.is_default ? '是' : '否'}</td>
              <td>
                <button onClick={() => handleEdit(config)}>编辑</button>
                <button onClick={() => handleDelete(config.id)}>删除</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {editingConfig && (
        <div>
          <h2>{editingConfig.id ? '编辑' : '添加'} 配置</h2>
          <label>
            别名:
            <input type="text" name="alias" value={editingConfig.alias} onChange={handleChange} />
          </label>
          <label>
            API 地址:
            <input type="text" name="api_endpoint" value={editingConfig.api_endpoint} onChange={handleChange} />
            <button onClick={handleFetchModels}>获取模型</button>
          </label>
          <label>
            模型:
            <select name="model" value={editingConfig.model} onChange={handleChange}>
              {availableModels.map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </label>
          <label>
            Temperature:
            <input type="number" name="temperature" value={editingConfig.temperature} onChange={handleChange} />
          </label>
          <label>
            Top P:
            <input type="number" name="top_p" value={editingConfig.top_p} onChange={handleChange} />
          </label>
          <label>
            默认:
            <input type="checkbox" name="is_default" checked={editingConfig.is_default} onChange={handleChange} />
          </label>
          <button onClick={handleSave}>保存</button>
          <button onClick={() => setEditingConfig(null)}>取消</button>
        </div>
      )}
    </div>
  );
};

export default SettingsPage;