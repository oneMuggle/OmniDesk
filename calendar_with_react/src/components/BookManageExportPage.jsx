import React, { useState, useEffect } from 'react';
import api from '../api/axiosConfig';

const BookManageExportPage = () => {
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
        <div className="book-manage-export-page">
            <h1>管理现有书籍</h1>

            {/* Manage Existing Books Section */}
            <div className="manage-books-section">
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

export default BookManageExportPage;