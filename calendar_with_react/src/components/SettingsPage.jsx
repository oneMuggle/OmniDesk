import React, { useState, useEffect } from 'react';
import { useApi } from '../context/ApiProvider';
import { setApiProvider } from '../api/deepseek';
import { saveResponsiblePersons } from '../api/responsiblePersons';

function SettingsPage() {
  const { apiConfig, setApiConfig, getModels } = useApi();
  const [formData, setFormData] = useState(apiConfig);
  const [apiType, setApiType] = useState(apiConfig.apiType || 'deepseek');
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
