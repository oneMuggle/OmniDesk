import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import './DifyApps.css'; // 稍后创建此CSS文件

const DifyAppViewer = () => {
    const { appId } = useParams();
    const [embedUrl, setEmbedUrl] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchAppDetails = async () => {
            try {
                // 假设后端API地址为 /api/dify-apps/{appId}/
                const authTokens = JSON.parse(localStorage.getItem('authTokens') || sessionStorage.getItem('authTokens') || '{}');
                const token = authTokens.access; // 从localStorage或sessionStorage获取Token
                const config = token ? {
                    headers: {
                        Authorization: `Bearer ${token}` // 添加Authorization头
                    }
                } : {};
                const response = await axios.get(`/api/dify-apps/${appId}/`, config);
                setEmbedUrl(response.data.embed_url);
            } catch (err) {
                setError('Failed to load Dify application.');
                console.error('Error fetching Dify app details:', err);
            } finally {
                setLoading(false);
            }
        };

        if (appId) {
            fetchAppDetails();
        } else {
            setError('Application ID is missing.');
            setLoading(false);
        }
    }, [appId]);

    if (loading) {
        return <div>Loading Dify Application...</div>;
    }

    if (error) {
        return <div className="error-message">{error}</div>;
    }

    if (!embedUrl) {
        return <div className="error-message">No embed URL found for this application.</div>;
    }

    return (
        <div className="dify-app-viewer-container">
            <h1>Viewing Dify Application</h1>
            <iframe
                src={embedUrl}
                title={`Dify Application ${appId}`}
                className="dify-iframe"
                allowFullScreen
            ></iframe>
        </div>
    );
};

export default DifyAppViewer;