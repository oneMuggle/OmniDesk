import React, { useState, useEffect } from 'react';
import { Layout, Input, Typography, message, Card, Row, Col, Space, Button } from 'antd';
import axios from 'axios';
import FileUpload from '../components/FileUpload';
import BookList from '../components/BookList';
import BookForm from '../components/BookForm';

const { Header, Content } = Layout;
const { Title } = Typography;
const EBookManagementPage = () => {
  const [books, setBooks] = useState([]);
  const [filteredBooks, setFilteredBooks] = useState([]);
  const [editingBook, setEditingBook] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const fetchBooks = async () => {
      setIsLoading(true);
      try {
        const response = await axios.get('/api/ebooks');
        setBooks(response.data);
        setFilteredBooks(response.data);
      } catch (error) {
        message.error('获取电子书列表失败');
      } finally {
        setIsLoading(false);
      }
    };

    fetchBooks();
  }, []);

  const handleSearch = (query) => {
    const lowercasedQuery = query.toLowerCase();
    const filtered = books.filter(book =>
      book.title.toLowerCase().includes(lowercasedQuery) ||
      book.author.toLowerCase().includes(lowercasedQuery)
    );
    setFilteredBooks(filtered);
  };

  const handleFileUpload = async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('/api/ebooks/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      const newBook = response.data;
      setBooks([...books, newBook]);
      setFilteredBooks([...books, newBook]);
      message.success(`'${file.name}' 导入成功`);
    } catch (error) {
      message.error('文件上传失败');
    }
  };

  const handleEdit = (book) => {
    setEditingBook(book);
  };

  const handleExport = (book) => {
    console.log('Exporting book:', book);
    message.info(`正在导出 '${book.title}'...`);
    // Implement export logic here
  };

  const handleSave = (updatedBook) => {
    setBooks((books || []).map(book => (book.id === updatedBook.id ? updatedBook : book)));
    setFilteredBooks((filteredBooks || []).map(book => (book.id === updatedBook.id ? updatedBook : book)));
    setEditingBook(null);
    message.success('电子书保存成功');
  };

  const handleDelete = async (bookId) => {
    try {
      await axios.delete(`/api/ebooks/${bookId}`);
      const updatedBooks = books.filter(book => book.id !== bookId);
      setBooks(updatedBooks);
      setFilteredBooks(updatedBooks);
      message.success('电子书删除成功');
    } catch (error) {
      message.error('删除电子书失败');
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ backgroundColor: '#fff', padding: '0 24px' }}>
        <Title level={3} style={{ margin: '16px 0' }}>电子书管理</Title>
      </Header>
      <Content style={{ padding: '24px' }}>
        <Card>
          <Row gutter={[16, 16]} align="middle">
            <Col>
              <FileUpload onFileUpload={handleFileUpload} />
            </Col>
            <Col flex="auto">
              <Space.Compact style={{ maxWidth: '400px' }}>
                <Input
                  placeholder="搜索电子书..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onPressEnter={() => handleSearch(searchQuery)}
                />
                <Button type="primary" onClick={() => handleSearch(searchQuery)}>
                  搜索
                </Button>
              </Space.Compact>
            </Col>
          </Row>
        </Card>
        <Card style={{ marginTop: '24px' }}>
          <BookList
            books={filteredBooks || []}
            onEdit={handleEdit}
            onDelete={handleDelete}
            onExport={handleExport}
            loading={isLoading}
          />
        </Card>
        {editingBook && (
          <BookForm
            book={editingBook}
            onSave={handleSave}
            onCancel={() => setEditingBook(null)}
          />
        )}
      </Content>
    </Layout>
  );
};

export default EBookManagementPage;