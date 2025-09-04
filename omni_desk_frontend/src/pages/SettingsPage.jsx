import React, { useState, useEffect } from 'react';
import { getOllamaConfigs, addOllamaConfig, updateOllamaConfig, deleteOllamaConfig, getOllamaModelsFromEndpoint } from '../api/ollama';

const SettingsPage = () => {
  const [configs, setConfigs] = useState([]);
  const [editingConfig, setEditingConfig] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);

  useEffect(() => {
    loadConfigs();
    // handleFetchModels 仅在用户点击“获取模型”按钮时调用，因为它依赖于 api_endpoint。
    // availableModels 的填充由用户手动触发。
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
    // 获取当前的 editingConfig
    const currentConfig = editingConfig;

    if (!currentConfig.model) {
      alert("请选择一个模型。");
      return;
    }

    // 检查 alias 是否已存在（仅在添加新配置时进行）
    // 如果 currentConfig.id 为空，表示是新增操作
    if (!currentConfig.id) {
      const aliasExists = configs.some(config => config.alias === currentConfig.alias);
      if (aliasExists) {
        alert("别名已存在，请选择一个不同的别名。");
        return;
      }
    }

    try {
      if (currentConfig.id) {
        await updateOllamaConfig(currentConfig.id, currentConfig);
      } else {
        await addOllamaConfig(currentConfig);
      }
      setEditingConfig(null); // 清空编辑中的配置
      loadConfigs(); // 重新加载配置列表
    } catch (error) {
      console.error("保存 Ollama 配置失败:", error);
      alert(`保存配置失败: ${error.message}`);
    }
  };

  const handleAddNew = () => {
    // 确保在创建新配置时，如果模型列表已加载，则默认选择第一个模型
    const defaultModel = availableModels.length > 0 ? availableModels[0] : '';
    setEditingConfig({
      alias: '',
      api_endpoint: '',
      model: defaultModel,
      temperature: 0.8,
      top_p: 0.9,
      is_default: false,
    });
    // 在添加新配置后，尝试立即获取模型列表
    // 这将确保 availableModels 在用户看到表单时尽可能快地被填充
    // 但需要确保 editingConfig.api_endpoint 已经设置
    if (editingConfig && editingConfig.api_endpoint) {
      handleFetchModels();
    }
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setEditingConfig(prevConfig => {
      let newValue = value;
      if (type === 'number') {
        newValue = parseFloat(value);
      } else if (type === 'checkbox') {
        newValue = checked;
      } else if (name === 'api_endpoint') {
        // 确保 api_endpoint 包含协议
        if (!newValue.startsWith('http://') && !newValue.startsWith('https://')) {
          newValue = `http://${newValue}`;
        }
      }
      return {
        ...prevConfig,
        [name]: newValue,
      };
    });
  };

  const handleFetchModels = async () => {
    if (editingConfig && editingConfig.api_endpoint) {
      try {
        const response = await getOllamaModelsFromEndpoint(editingConfig.api_endpoint);
        // Ollama API 返回的格式是 { object: "list", data: [...] }，其中 data 包含模型信息
        // Ollama API 的 /v1/models 接口返回的模型对象中，模型名称在 'id' 字段
        // 而 /tags 接口返回的模型对象中，模型名称在 'name' 字段
        // 为了兼容性，这里假设后端需要的是模型名称，即 'id' 字段的值
        const models = response.data.map(model => model.id);
        setAvailableModels(models);
        console.log("Available Models:", models);

        // 如果当前没有选择模型，并且有可用模型，则自动选择第一个
        if (!editingConfig.model && models.length > 0) {
          setEditingConfig(prevConfig => ({
            ...prevConfig,
            model: models[0],
          }));
        }
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