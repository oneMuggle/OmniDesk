import React, { useState, useEffect } from 'react';
import apiClient from '../../api/apiClient';
import './DifyAppManagementPage.css';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faEdit, faTrash, faPlus, faTimes } from '@fortawesome/free-solid-svg-icons';

const DifyAppManagementPage = () => {
    const [difyApps, setDifyApps] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [showForm, setShowForm] = useState(false);
    const [currentApp, setCurrentApp] = useState(null); // For editing

    const [formData, setFormData] = useState({
        name: '',
        description: '',
        embed_url: ''
    });

    const fetchDifyApps = async () => {
        try {
            const response = await apiClient.get('/dify-apps/');
            setDifyApps(response.data.results || response.data); // Adjust based on API response structure
        } catch (err) {
            setError('Failed to fetch Dify applications.');
            console.error('Error fetching Dify apps:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDifyApps();
    }, []);

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData({ ...formData, [name]: value });
    };

    const handleAddClick = () => {
        setCurrentApp(null);
        setFormData({ name: '', description: '', embed_url: '' });
        setShowForm(true);
    };

    const handleEditClick = (app) => {
        setCurrentApp(app);
        setFormData({
            name: app.name,
            description: app.description,
            embed_url: app.embed_url
        });
        setShowForm(true);
    };

    const handleDeleteClick = async (appId) => {
        if (window.confirm('Are you sure you want to delete this Dify application?')) {
            try {
                await apiClient.delete(`/dify-apps/${appId}/`);
                fetchDifyApps(); // Refresh list
            } catch (err) {
                setError('Failed to delete Dify application.');
                console.error('Error deleting Dify app:', err);
            }
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            if (currentApp) {
                // Update existing app
                await apiClient.put(`/dify-apps/${currentApp.id}/`, formData);
            } else {
                // Create new app
                await apiClient.post('/dify-apps/', formData);
            }
            setShowForm(false);
            fetchDifyApps(); // Refresh list
        } catch (err) {
            setError('Failed to save Dify application.');
            console.error('Error saving Dify app:', err);
        }
    };

    if (loading) {
        return <div>Loading Dify Applications...</div>;
    }

    if (error) {
        return <div className="error-message">{error}</div>;
    }

    return (
        <div className="dify-app-management-container">
            <h1>Dify 应用管理</h1>

            <button className="add-button" onClick={handleAddClick}>
                <FontAwesomeIcon icon={faPlus} /> 添加 Dify 应用
            </button>

            {showForm && (
                <div className="form-modal-overlay">
                    <div className="form-modal">
                        <div className="form-modal-header">
                            <h2>{currentApp ? '编辑 Dify 应用' : '添加 Dify 应用'}</h2>
                            <button className="close-button" onClick={() => setShowForm(false)}>
                                <FontAwesomeIcon icon={faTimes} />
                            </button>
                        </div>
                        <form onSubmit={handleSubmit}>
                            <div className="form-group">
                                <label htmlFor="name">名称:</label>
                                <input
                                    type="text"
                                    id="name"
                                    name="name"
                                    value={formData.name}
                                    onChange={handleInputChange}
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label htmlFor="description">描述:</label>
                                <textarea
                                    id="description"
                                    name="description"
                                    value={formData.description}
                                    onChange={handleInputChange}
                                ></textarea>
                            </div>
                            <div className="form-group">
                                <label htmlFor="embed_url">嵌入 URL:</label>
                                <input
                                    type="url"
                                    id="embed_url"
                                    name="embed_url"
                                    value={formData.embed_url}
                                    onChange={handleInputChange}
                                    required
                                />
                            </div>
                            <button type="submit" className="submit-button">
                                {currentApp ? '更新' : '添加'}
                            </button>
                        </form>
                    </div>
                </div>
            )}

            <table className="dify-app-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>名称</th>
                        <th>描述</th>
                        <th>嵌入 URL</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    {difyApps.length === 0 ? (
                        <tr>
                            <td colSpan="5">没有找到 Dify 应用。</td>
                        </tr>
                    ) : (
                        difyApps.map(app => (
                            <tr key={app.id}>
                                <td>{app.id}</td>
                                <td>{app.name}</td>
                                <td>{app.description}</td>
                                <td><a href={app.embed_url} target="_blank" rel="noopener noreferrer">{app.embed_url}</a></td>
                                <td>
                                    <button className="action-button edit" onClick={() => handleEditClick(app)}>
                                        <FontAwesomeIcon icon={faEdit} /> 编辑
                                    </button>
                                    <button className="action-button delete" onClick={() => handleDeleteClick(app.id)}>
                                        <FontAwesomeIcon icon={faTrash} /> 删除
                                    </button>
                                </td>
                            </tr>
                        ))
                    )}
                </tbody>
            </table>
        </div>
    );
};

export default DifyAppManagementPage;