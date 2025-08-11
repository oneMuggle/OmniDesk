import React, { useState, useEffect, useLayoutEffect } from 'react';
import { useParams, useLocation } from 'react-router-dom';
import { Spin, Typography } from 'antd';
import axios from 'axios';

const { Title } = Typography;

const ChapterContent = () => {
    const { chapterId } = useParams();
    const location = useLocation();
    const [chapter, setChapter] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (!chapterId) {
            setChapter(null);
            setLoading(false);
            return;
        }

        const fetchChapter = async () => {
            setLoading(true);
            try {
                // Assuming API endpoint is /api/documents/chapters/<id>/
                const response = await axios.get(`/api/documents/chapters/${chapterId}/`);
                setChapter(response.data);
            } catch (err) {
                setError('Failed to load chapter content.');
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        fetchChapter();
    }, [chapterId]);

    useLayoutEffect(() => {
        if (location.hash && chapter) {
            const id = location.hash.replace('#', '');
            const element = document.getElementById(id);
            if (element) {
                element.scrollIntoView({ behavior: 'smooth' });
            }
        }
    }, [location.hash, chapter]);

    if (!chapterId) {
        return <Title level={2}>Please select a chapter to read.</Title>;
    }

    if (loading) {
        return <Spin size="large" />;
    }

    if (error) {
        return <div style={{ color: 'red' }}>{error}</div>;
    }

    if (!chapter) {
        return null;
    }

    return (
        <div className="chapter-content">
            <Title level={1}>{chapter.title}</Title>
            <div dangerouslySetInnerHTML={{ __html: chapter.content_html }} />
        </div>
    );
};

export default ChapterContent;