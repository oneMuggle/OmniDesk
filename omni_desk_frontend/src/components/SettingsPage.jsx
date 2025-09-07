import React, { useState, useEffect } from 'react';
import { useApi } from '../context/ApiProvider';
import { setApiProvider } from '../api/deepseek';
import { saveResponsiblePersons } from '../api/responsiblePersons';
import { getConfig, setConfig } from '../api/ollama';
import apiClient from '../api/apiClient'; // 导入 apiClient

function SettingsPage() {
  const { apiConfig, setApiConfig, getModels } = useApi();
  const [formData, setFormData] = useState(apiConfig);
  const [apiType, setApiType] = useState(apiConfig.apiType || 'deepseek');
  const [ollamaEndpoint, setOllamaEndpoint] = useState('');
  const [ragflowConfigs, setRagflowConfigs] = useState([]); // 新增：存储 Ragflow 配置列表
  const [selectedRagflowConfig, setSelectedRagflowConfig] = useState(null); // 新增：当前编辑的 Ragflow 配置
  const [newRagflowConfig, setNewRagflowConfig] = useState({ name: '', api_endpoint: '', api_key: '', is_active: true }); // 新增：用于新增 Ragflow 配置的表单数据

  useEffect(() => {
    // 获取当前的OLLAMA端点配置
    const fetchOllamaConfig = async () => {
      try {
        const config = await getConfig();
        setOllamaEndpoint(config.OLLAMA_ENDPOINT || '');
      } catch (error) {
        console.error('获取OLLAMA配置失败:', error);
      }
    };
    fetchOllamaConfig();

    // 新增：获取所有Ragflow配置
    const fetchRagflowConfigs = async () => {
      try {
        const response = await apiClient.get('/ragflow-service/configs/');
        setRagflowConfigs(response.data.results || []);
      } catch (error) {
        console.error('Error fetching Ragflow configs:', error);
      }
    };
    fetchRagflowConfigs();
  }, []);
  const [models, setModels] = useState([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [modelError, setModelError] = useState('');
  const [responsiblePersons, setResponsiblePersons] = useState([]);
  const [newPerson, setNewPerson] = useState({
    name: '',
    department: '',
    contact: '',
    event: ''
  });

  // 负责人管理逻辑
  const handleAddPerson = () => {
    if (newPerson.name && newPerson.department) {
      setResponsiblePersons([...responsiblePersons, { ...newPerson, id: Date.now() }]);
      setNewPerson({ name: '', department: '', contact: '', event: '' });
    }
  };

  const handleRemovePerson = (id) => {
    setResponsiblePersons(responsiblePersons.filter(person => person.id !== id));
  };

  const handleSaveResponsibles = async () => {
    try {
      await saveResponsiblePersons(responsiblePersons);
      setResponsiblePersons([]);
      alert('保存成功');
    } catch (error) {
      console.error('保存失败:', error);
      alert(error.message);
    }
  };

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
            <option value="ragflow">Ragflow</option>
            <option value="dify">Dify</option>
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

      {apiType === 'ollama' && (
        <div className="settings-section">
          <h3>OLLAMA 服务器配置</h3>
          <div className="form-group">
            <label>当前端点:</label>
            <input
              type="text"
              value={ollamaEndpoint}
              readOnly
            />
          </div>
          <button
            type="button"
            onClick={async () => {
              try {
                await setConfig({
                  OLLAMA_ENDPOINT: formData.apiEndpoint
                });
                setOllamaEndpoint(formData.apiEndpoint);
                alert('OLLAMA端点配置已保存');
              } catch (error) {
                console.error('保存OLLAMA配置失败:', error);
                alert('保存失败: ' + error.message);
              }
            }}
          >
            保存OLLAMA端点
          </button>
        </div>
      )}

      {apiType === 'ragflow' && (
        <div className="settings-section">
          <h3>Ragflow 配置管理</h3>
          <div className="form-group">
            <label htmlFor="ragflow-config-select">选择现有配置:</label>
            <select
              id="ragflow-config-select"
              value={selectedRagflowConfig ? selectedRagflowConfig.id : ''}
              onChange={(e) => {
                const config = ragflowConfigs.find(c => c.id === parseInt(e.target.value));
                setSelectedRagflowConfig(config);
                setNewRagflowConfig(config ? { ...config } : { name: '', api_endpoint: '', api_key: '', is_active: true });
              }}
            >
              <option value="">-- 新增配置 --</option>
              {ragflowConfigs.map(config => (
                <option key={config.id} value={config.id}>{config.name}</option>
              ))}
            </select>
          </div>

          <form onSubmit={async (e) => {
            e.preventDefault();
            try {
              if (selectedRagflowConfig) {
                // 更新现有配置
                await apiClient.put(`/ragflow-service/configs/${selectedRagflowConfig.id}/`, newRagflowConfig);
                alert('Ragflow 配置更新成功！');
              } else {
                // 新增配置
                await apiClient.post('/ragflow-service/configs/', newRagflowConfig);
                alert('Ragflow 配置新增成功！');
              }
              // 重新获取配置列表
              const response = await apiClient.get('/ragflow-service/configs/');
              setRagflowConfigs(response.data.results || []);
              setSelectedRagflowConfig(null);
              setNewRagflowConfig({ name: '', api_endpoint: '', api_key: '', is_active: true });
            } catch (error) {
              console.error('保存 Ragflow 配置失败:', error);
              alert(`保存 Ragflow 配置失败: ${error.response?.data?.detail || error.message}`);
            }
          }}>
            <div className="form-group">
              <label>配置名称:</label>
              <input
                type="text"
                value={newRagflowConfig.name}
                onChange={(e) => setNewRagflowConfig({ ...newRagflowConfig, name: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>API 端点:</label>
              <input
                type="url"
                value={newRagflowConfig.api_endpoint}
                onChange={(e) => setNewRagflowConfig({ ...newRagflowConfig, api_endpoint: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>API 密钥:</label>
              <input
                type="text"
                value={newRagflowConfig.api_key}
                onChange={(e) => setNewRagflowConfig({ ...newRagflowConfig, api_key: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>是否激活:</label>
              <input
                type="checkbox"
                checked={newRagflowConfig.is_active}
                onChange={(e) => setNewRagflowConfig({ ...newRagflowConfig, is_active: e.target.checked })}
              />
            </div>
            <button type="submit">
              {selectedRagflowConfig ? '更新配置' : '新增配置'}
            </button>
            {selectedRagflowConfig && (
              <button
                type="button"
                onClick={async () => {
                  if (window.confirm('确定要删除此配置吗？')) {
                    try {
                      await apiClient.delete(`/ragflow-service/configs/${selectedRagflowConfig.id}/`);
                      alert('Ragflow 配置删除成功！');
                      const response = await apiClient.get('/ragflow-service/configs/');
                      setRagflowConfigs(response.data.results || []);
                      setSelectedRagflowConfig(null);
                      setNewRagflowConfig({ name: '', api_endpoint: '', api_key: '', is_active: true });
                    } catch (error) {
                      console.error('删除 Ragflow 配置失败:', error);
                      alert(`删除 Ragflow 配置失败: ${error.response?.data?.detail || error.message}`);
                    }
                  }
                }}
              >
                删除配置
              </button>
            )}
          </form>
        </div>
      )}

      <div className="settings-section">
        <h3>负责人管理</h3>
        <div className="responsible-form">
          <input
            type="text"
            placeholder="姓名"
            name="name"
            value={newPerson.name || ''}
            onChange={(e) => setNewPerson({...newPerson, name: e.target.value})}
          />
          <input
            type="text"
            placeholder="职位"
            name="department"
            value={newPerson.department || ''}
            onChange={(e) => setNewPerson({...newPerson, department: e.target.value})}
          />
          <input
            type="text"
            placeholder="联系方式"
            name="contact"
            value={newPerson.contact || ''}
            onChange={(e) => setNewPerson({...newPerson, contact: e.target.value})}
          />
          <button type="button" onClick={handleAddPerson}>添加负责人</button>
          <input
            type="number"
            placeholder="关联事件ID"
            name="event"
            value={newPerson.event || ''}
            onChange={(e) => setNewPerson({...newPerson, event: e.target.value})}
          />
        </div>
        
        <div className="responsible-list">
          {responsiblePersons.map((person) => (
            <div key={person.id} className="responsible-item">
              <span>{person.name}</span>
              <span>{person.department}</span>
              <span>{person.contact}</span>
              <span>事件ID: {person.event}</span>
              <button type="button" onClick={() => handleRemovePerson(person.id)}>删除</button>
            </div>
          ))}
        </div>

        <button
          type="button"
          className="save-button"
          onClick={handleSaveResponsibles}
        >
          保存到服务器
        </button>
      </div>
    </div>
  );
}


export default SettingsPage;
