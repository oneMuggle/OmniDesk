import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import api from '../api/apiClient';
import './LibraryPage.css';

const BookCard = ({ book }) => (
    <a href={`/read-book/${book.id}`} target="_blank" rel="noopener noreferrer" className="book-card">
        <img
            src={book.cover_image || '/default-cover.png'}
            alt={`${book.title} cover`}
            className="book-cover"
        />
        <div className="book-info">
            <h3 className="book-title">{book.title}</h3>
            <p className="book-author">{book.author || '未知作者'}</p>
            <div className="book-tags">
                {book.tags && book.tags.map(tag => (
                    <span key={tag.id} className="tag">{tag.name}</span>
                ))}
            </div>
        </div>
    </a>
);

BookCard.propTypes = {
  book: PropTypes.shape({
    id: PropTypes.number.isRequired,
    cover_image: PropTypes.string,
    title: PropTypes.string.isRequired,
    author: PropTypes.string,
    tags: PropTypes.arrayOf(PropTypes.shape({
      id: PropTypes.number,
      name: PropTypes.string,
    })),
  }).isRequired,
};

const LibraryPage = () => {
    const [books, setBooks] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchBooks = async () => {
            try {
                const response = await api.get('/api/documents/books/');
                setBooks(response.data.results || response.data); // Handle paginated or non-paginated response
                setLoading(false);
            } catch (err) {
                setError('无法加载书籍列表，请稍后再试。');
                setLoading(false);
            }
        };

        fetchBooks();
    }, []);

    if (loading) {
        return <div className="library-status">正在加载...</div>;
    }

    if (error) {
        return <div className="library-status error">{error}</div>;
    }

    return (
        <div className="library-page">
            <h1>书库</h1>
            <div className="book-grid">
                {books.length > 0 ? (
                    books.map(book => <BookCard key={book.id} book={book} />)
                ) : (
                    <p>书库中还没有任何书籍。</p>
                )}
            </div>
        </div>
    );
};

export default LibraryPage;