import React, { useState, useEffect } from 'react';
import api from '../api/axiosConfig';
import './BookImportPage.css'; // Reusing some CSS, may create BookManagementPage.css later

const BookManagementPage = () => {
    // State for book import form
    const [markdownFile, setMarkdownFile] = useState(null);
    const [coverImage, setCoverImage] = useState(null);
    const [title, setTitle] = useState('');
    const [author, setAuthor] = useState('');
    const [description, setDescription] = useState('');
    const [tags, setTags] = useState('');
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');

    // State for managing existing books
    const [books, setBooks] = useState([]);
    const [loadingBooks, setLoadingBooks] = useState(true);
    const [booksError, setBooksError] = useState(null);

    useEffect(() => {
        fetchBooks();
    }, []);

    const fetchBooks = async () => {
        try {
            setLoadingBooks(true);
            const response = await api.get('/api/documents/books/');
            setBooks(response.data.results || response.data);
            setLoadingBooks(false);
        } catch (err) {
            setBooksError('无法加载书籍列表，请稍后再试。');
            setLoadingBooks(false);
        }
    };

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
            fetchBooks(); // Refresh book list after import
        } catch (err) {
            console.error('导入失败:', err.response || err);
            setError(err.response?.data?.error || '书籍导入失败，请检查文件和输入。');
        }
    };

    const handleExportMarkdown = async (bookId, bookTitle) => {
        try {
            const response = await api.get(`/api/documents/books/${bookId}/export_markdown/`, {
                responseType: 'blob',
            });

            const blob = new Blob([response.data], { type: 'text/markdown' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `${bookTitle}.md`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(link.href);
            alert(`书籍 "${bookTitle}" 导出成功！`);
        } catch (error) {
            console.error('Error exporting markdown:', error);
            alert('导出Markdown失败，请稍后再试。');
        }
    };

    const handleDeleteBook = async (bookId, bookTitle) => {
        if (window.confirm(`确定要删除书籍 "${bookTitle}" 吗？`)) {
            try {
                await api.delete(`/api/documents/books/${bookId}/`);
                alert(`书籍 "${bookTitle}" 删除成功！`);
                fetchBooks(); // Refresh book list after delete
            } catch (error) {
                console.error('Error deleting book:', error);
                alert('删除书籍失败，请稍后再试。');
            }
        }
    };

    return (
        <div className="book-management-page">
            <h1>书籍管理</h1>

            {/* Import Book Section */}
            <div className="import-section">
                <h2>导入新书籍</h2>
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

            {/* Manage Existing Books Section */}
            <div className="manage-books-section">
                <h2>管理现有书籍</h2>
                {loadingBooks ? (
                    <p>正在加载书籍...</p>
                ) : booksError ? (
                    <p className="error-message">{booksError}</p>
                ) : books.length === 0 ? (
                    <p>目前没有已导入的书籍。</p>
                ) : (
                    <div className="books-list">
                        {books.map(book => (
                            <div key={book.id} className="book-item">
                                <h3>{book.title}</h3>
                                <p>作者: {book.author}</p>
                                <div className="book-actions">
                                    {/* Edit functionality will go here */}
                                    <button onClick={() => handleExportMarkdown(book.id, book.title)}>导出</button>
                                    <button onClick={() => handleDeleteBook(book.id, book.title)} className="delete-button">删除</button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default BookManagementPage;