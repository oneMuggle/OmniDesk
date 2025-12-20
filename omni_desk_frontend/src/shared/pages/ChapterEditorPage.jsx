import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api/axiosConfig';
import './ChapterEditorPage.css';

const ChapterEditorPage = () => {
    const { chapterId } = useParams();
    const [chapter, setChapter] = useState(null);
    const [contentMd, setContentMd] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [message, setMessage] = useState('');

    useEffect(() => {
        const fetchChapter = async () => {
            try {
                const response = await api.get(`/api/documents/chapters/${chapterId}/`);
                setChapter(response.data);
                setContentMd(response.data.content_md);
                setLoading(false);
            } catch (err) {
                setError('无法加载章节内容进行编辑。');
                setLoading(false);
            }
        };
        fetchChapter();
    }, [chapterId]);

    const handleSave = async () => {
        setMessage('');
        setError('');
        try {
            await api.put(`/api/documents/chapters/${chapterId}/update_content/`, {
                content_md: contentMd,
            });
            setMessage('章节内容更新成功！');
            // Optionally navigate back to the book page or show a success message
            // navigate(`/books/${bookId}`);
        } catch (err) {
            setError(err.response?.data?.error || '保存失败，请重试。');
        }
    };

    if (loading) {
        return <div className="editor-status">正在加载章节...</div>;
    }

    if (error) {
        return <div className="editor-status error">{error}</div>;
    }

    return (
        <div className="chapter-editor-page">
            <h1>编辑章节: {chapter?.title}</h1>
            <textarea
                className="markdown-editor"
                value={contentMd}
                onChange={(e) => setContentMd(e.target.value)}
                rows="20"
                placeholder="在此输入Markdown内容..."
            />
            <button onClick={handleSave} className="save-button">保存更改</button>
            {message && <p className="success-message">{message}</p>}
            {error && <p className="error-message">{error}</p>}
        </div>
    );
};

export default ChapterEditorPage;