import './DifyApps.css';
import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axiosInstance from '../../../shared/api/axiosConfig';
import { logger } from '../../../shared/utils/logger';
import { readAuthTokens } from '../../../shared/utils/authTokens';

const DifyAppViewer = () => {
    const { appId } = useParams();
    const [embedUrl, setEmbedUrl] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchAppDetails = async () => {
            try {
                const token = readAuthTokens()?.access;
                if (!token) {
                    throw new Error('AUTH_ERROR');
                }
                const response = await axiosInstance.get(`dify-apps/${appId}/`);
                const nextEmbedUrl = response.data?.embed_url;
                if (typeof nextEmbedUrl !== 'string' || !nextEmbedUrl.trim()) {
                    throw new Error('INVALID_RESPONSE');
                }
                setEmbedUrl(nextEmbedUrl);
            } catch (err) {
                setError(err.message === 'AUTH_ERROR'
                    ? '认证已过期，请重新登录'
                    : '无法加载 Dify 应用，请稍后重试');
                logger.error('Error fetching Dify app details:', err);
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