import React, { useState, useEffect } from 'react';
import { Layout, Input, Typography, message, Card, Row, Col } from 'antd';
import FileUpload from '../components/EBook/FileUpload';
import BookList from '../components/EBook/BookList';
import BookForm from '../components/EBook/BookForm';

const { Header, Content } = Layout;
const { Title } = Typography;
const { Search } = Input;

const EBookManagementPage = () => {
  const [books, setBooks] = useState([]);
  const [filteredBooks, setFilteredBooks] = useState([]);
  const [editingBook, setEditingBook] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Mock data for initial display
  const mockBooks = [
    { id: 1, title: 'React 入门指南', author: '张三', createdAt: '2023-10-01' },
    { id: 2, title: 'Vue.js 深度剖析', author: '李四', createdAt: '2023-09-15' },
    { id: 3, title: 'JavaScript 高级编程', author: '王五', createdAt: '2023-11-01' },
  ];

  useEffect(() => {
    // Simulate fetching data from an API
    setTimeout(() => {
      setBooks(mockBooks);
      setFilteredBooks(mockBooks);
      setIsLoading(false);
    }, 1000);
  }, []);

  const handleSearch = (query) => {
    const lowercasedQuery = query.toLowerCase();
    const filtered = books.filter(book =>
      book.title.toLowerCase().includes(lowercasedQuery) ||
      book.author.toLowerCase().includes(lowercasedQuery)
    );
    setFilteredBooks(filtered);
  };

  const handleFileUpload = (file) => {
    const newBook = {
      id: books.length + 1,
      title: file.name.replace(/\.md$/, ''),
      author: '未知作者',
      createdAt: new Date().toISOString().split('T')[0],
    };
    setBooks([...books, newBook]);
    setFilteredBooks([...books, newBook]);
    message.success(`'${file.name}' 导入成功`);
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
              <Search
                placeholder="搜索电子书..."
                onSearch={handleSearch}
                enterButton
                style={{ maxWidth: '400px' }}
              />
            </Col>
          </Row>
        </Card>
        <Card style={{ marginTop: '24px' }}>
          <BookList
            books={filteredBooks || []}
            onEdit={handleEdit}
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