import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import './DifyApps.css'; // 稍后创建此CSS文件

const DifyAppList = () => {
    const [difyApps, setDifyApps] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const navigate = useNavigate();

    useEffect(() => {
        const fetchDifyApps = async () => {
            try {
                // 假设后端API地址为 /api/dify-apps/
                const response = await axios.get('/api/dify-apps/');
                setDifyApps(response.data);
            } catch (err) {
                setError('Failed to fetch Dify applications.');
                console.error('Error fetching Dify apps:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchDifyApps();
    }, []);

    const handleAppClick = (appId) => {
        navigate(`/dify-apps/${appId}`);
    };

    if (loading) {
        return <div>Loading Dify Applications...</div>;
    }

    if (error) {
        return <div className="error-message">{error}</div>;
    }

    return (
        <div className="dify-app-list-container">
            <h1>Dify Applications</h1>
            <div className="dify-app-grid">
                {difyApps.length === 0 ? (
                    <p>No Dify applications found.</p>
                ) : (
                    difyApps.map(app => (
                        <div key={app.id} className="dify-app-card" onClick={() => handleAppClick(app.id)}>
                            <h2>{app.name}</h2>
                            <p>{app.description}</p>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default DifyAppList;