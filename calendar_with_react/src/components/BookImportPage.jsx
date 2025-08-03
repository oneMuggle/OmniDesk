import React, { useState } from 'react';
import api from '../api/axiosConfig';
import './BookImportPage.css';

const BookImportPage = () => {
    const [markdownFile, setMarkdownFile] = useState(null);
    const [coverImage, setCoverImage] = useState(null);
    const [title, setTitle] = useState('');
    const [author, setAuthor] = useState('');
    const [description, setDescription] = useState('');
    const [tags, setTags] = useState('');
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');

    const handleFileChange = (e) => {
        setMarkdownFile(e.target.files[0]);
    };

    const handleCoverImageChange = (e) => {
        setCoverImage(e.target.files[0]);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setMessage('');
        setError('');

        if (!markdownFile) {
            setError('请选择一个Markdown文件。');
            return;
        }

        const formData = new FormData();
        formData.append('markdown_file', markdownFile);
        if (coverImage) {
            formData.append('cover_image', coverImage);
        }
        formData.append('title', title);
        formData.append('author', author);
        formData.append('description', description);
        formData.append('tags', tags);

        try {
            const response = await api.post('/api/documents/import_book/', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });
            setMessage(response.data.message || '书籍导入成功！');
            // Clear form
            setMarkdownFile(null);
            setCoverImage(null);
            setTitle('');
            setAuthor('');
            setDescription('');
            setTags('');
            document.getElementById('markdownFileInput').value = '';
            document.getElementById('coverImageInput').value = '';

        } catch (err) {
            console.error('导入失败:', err.response || err);
            setError(err.response?.data?.error || '书籍导入失败，请检查文件和输入。');
        }
    };

    return (
        <div className="book-import-page">
            <h1>导入书籍</h1>
            <form onSubmit={handleSubmit} className="import-form">
                <div className="form-group">
                    <label htmlFor="markdownFileInput">Markdown 文件:</label>
                    <input 
                        type="file" 
                        id="markdownFileInput" 
                        accept=".md" 
                        onChange={handleFileChange} 
                        required 
                    />
                </div>
                <div className="form-group">
                    <label htmlFor="coverImageInput">封面图片 (可选):</label>
                    <input 
                        type="file" 
                        id="coverImageInput" 
                        accept="image/*" 
                        onChange={handleCoverImageChange} 
                    />
                </div>
                <div className="form-group">
                    <label htmlFor="titleInput">书名:</label>
                    <input 
                        type="text" 
                        id="titleInput" 
                        value={title} 
                        onChange={(e) => setTitle(e.target.value)} 
                        placeholder="请输入书名"
                        required 
                    />
                </div>
                <div className="form-group">
                    <label htmlFor="authorInput">作者 (可选):</label>
                    <input 
                        type="text" 
                        id="authorInput" 
                        value={author} 
                        onChange={(e) => setAuthor(e.target.value)} 
                        placeholder="请输入作者"
                    />
                </div>
                <div className="form-group">
                    <label htmlFor="descriptionInput">简介 (可选):</label>
                    <textarea 
                        id="descriptionInput" 
                        value={description} 
                        onChange={(e) => setDescription(e.target.value)} 
                        placeholder="请输入书籍简介"
                        rows="4"
                    />
                </div>
                <div className="form-group">
                    <label htmlFor="tagsInput">标签 (逗号分隔, 可选):</label>
                    <input 
                        type="text" 
                        id="tagsInput" 
                        value={tags} 
                        onChange={(e) => setTags(e.target.value)} 
                        placeholder="例如: 科幻, 历史, 编程"
                    />
                </div>
                
                <button type="submit">导入书籍</button>

                {message && <p className="success-message">{message}</p>}
                {error && <p className="error-message">{error}</p>}
            </form>
        </div>
    );
};

export default BookImportPage;