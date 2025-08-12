import React, { useState, useEffect } from 'react';
import api from '../api/axiosConfig';
import projectsApi from '../api/projects'; // Import projectsApi
import { Select } from 'antd'; // Import Select for project filtering
import './LibraryPage.css';

const { Option } = Select; // Destructure Option

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
            {book.project_name && <p className="book-project">项目: {book.project_name}</p>}
            <div className="book-tags">
                {book.tags && book.tags.map(tag => (
                    <span key={tag.id} className="tag">{tag.name}</span>
                ))}
            </div>
        </div>
    </a>
);

const LibraryPage = () => {
    const [books, setBooks] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [projects, setProjects] = useState([]); // Add projects state
    const [selectedProject, setSelectedProject] = useState(null); // Add selectedProject state

    useEffect(() => {
        const fetchInitialData = async () => {
            try {
                const [booksResponse, projectsResponse] = await Promise.all([
                    api.get('/api/documents/books/'),
                    projectsApi.getAllProjects()
                ]);
                setBooks(booksResponse.data.results || booksResponse.data);
                setProjects(projectsResponse.data);
                setLoading(false);
            } catch (err) {
                setError('无法加载数据，请稍后再试。');
                setLoading(false);
            }
        };

        fetchInitialData();
    }, []);

    useEffect(() => {
        const fetchBooksByProject = async () => {
            setLoading(true);
            try {
                const url = selectedProject
                    ? `/api/documents/books/?project=${selectedProject}`
                    : '/api/documents/books/';
                const response = await api.get(url);
                setBooks(response.data.results || response.data);
                setLoading(false);
            } catch (err) {
                setError('无法加载书籍列表，请稍后再试。');
                setLoading(false);
            }
        };

        fetchBooksByProject();
    }, [selectedProject]); // Re-fetch books when selectedProject changes

    if (loading) {
        return <div className="library-status">正在加载...</div>;
    }

    if (error) {
        return <div className="library-status error">{error}</div>;
    }

    return (
        <div className="library-page">
            <h1>书库</h1>
            <div className="library-controls">
                <label htmlFor="project-select">选择项目：</label>
                <Select
                    id="project-select"
                    style={{ width: 200 }}
                    placeholder="请选择项目"
                    onChange={(value) => setSelectedProject(value)}
                    value={selectedProject}
                    allowClear
                >
                    {projects.map(project => (
                        <Option key={project.id} value={project.id}>{project.name}</Option>
                    ))}
                </Select>
            </div>
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