import React, { useState, useEffect } from 'react';
import { Layout, Spin } from 'antd';
import axios from 'axios';

import TableOfContents from './TableOfContents';
import ChapterContent from './ChapterContent';

const { Sider, Content } = Layout;

const LibraryPage = () => {
    const [books, setBooks] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchBooks = async () => {
            try {
                // Assuming you have an API endpoint to fetch all books with their chapters and heading structures
                const response = await axios.get('/api/documents/books/');
                setBooks(response.data);
            } catch (err) {
                setError('Failed to load books.');
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        fetchBooks();
    }, []);

    if (loading) {
        return <Spin size="large" />;
    }

    if (error) {
        return <div style={{ color: 'red' }}>{error}</div>;
    }

    return (
        <Layout style={{ minHeight: '100vh' }}>
            <Sider width={300} theme="light">
                <h2>Library</h2>
                <TableOfContents books={books} />
            </Sider>
            <Layout>
                <Content style={{ padding: '24px', margin: 0, backgroundColor: '#fff' }}>
                    <ChapterContent />
                </Content>
            </Layout>
        </Layout>
    );
};

export default LibraryPage;