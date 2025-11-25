import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import EBookManagementPage from './EBookManagementPage';

test('renders EBookManagementPage and displays title', async () => {
  render(<EBookManagementPage />);
  
  const titleElement = screen.getByText(/电子书管理/i);
  expect(titleElement).toBeInTheDocument();
  
  await waitFor(() => {
    expect(screen.queryByText(/加载中.../i)).not.toBeInTheDocument();
  }, { timeout: 2000 });
  
  const bookTitleElement = await screen.findByText(/React 入门指南/i);
  expect(bookTitleElement).toBeInTheDocument();
});

test('uploads a new book and displays it in the list', async () => {
  render(<EBookManagementPage />);
  
  await screen.findByText('React 入门指南'); // Wait for initial data

  const file = new File(['hello'], 'hello.md', { type: 'text/markdown' });
  const input = screen.getByLabelText('选择文件').querySelector('input');

  await userEvent.upload(input, file);

  await screen.findByText('hello');
  await screen.findByText(/导入成功/);
});

test('opens the edit form with the correct book data', async () => {
  render(<EBookManagementPage />);

  const editButton = await screen.findByLabelText('edit-book-1');
  await userEvent.click(editButton);

  const titleInput = await screen.findByLabelText(/书名/i);
  const authorInput = await screen.findByLabelText(/作者/i);

  expect(titleInput).toHaveValue('React 入门指南');
  expect(authorInput).toHaveValue('张三');
});

test('edits a book and updates the list', async () => {
  render(<EBookManagementPage />);

  const editButton = await screen.findByLabelText('edit-book-1');
  await userEvent.click(editButton);

  const titleInput = await screen.findByLabelText(/书名/i);
  const authorInput = await screen.findByLabelText(/作者/i);

  await userEvent.clear(titleInput);
  await userEvent.type(titleInput, 'React 高级指南');
  await userEvent.clear(authorInput);
  await userEvent.type(authorInput, '李四二世');

  const saveButton = screen.getByRole('button', { name: /保存/i });
  await userEvent.click(saveButton);

  const updatedTitleElement = await screen.findByText(/React 高级指南/i);
  const updatedAuthorElement = await screen.findByText(/李四二世/i);

  expect(updatedTitleElement).toBeInTheDocument();
  expect(updatedAuthorElement).toBeInTheDocument();
});

test('searches for books by title and author', async () => {
  render(<EBookManagementPage />);
  await screen.findByText('React 入门指南'); // Wait for initial data

  const searchInput = screen.getByPlaceholderText(/搜索电子书.../i);
  const searchButton = screen.getByRole('button', { name: /search/i });

  await userEvent.type(searchInput, 'React');
  await userEvent.click(searchButton);
  
  await screen.findByText(/React 入门指南/i);
  expect(screen.queryByText(/Vue.js 深度剖析/i)).not.toBeInTheDocument();

  await userEvent.clear(searchInput);
  await userEvent.type(searchInput, '王五');
  await userEvent.click(searchButton);

  await screen.findByText(/JavaScript 高级编程/i);
  expect(screen.queryByText(/React 入门指南/i)).not.toBeInTheDocument();
});

test('calls the onExport function when the export button is clicked', async () => {
  const consoleSpy = jest.spyOn(console, 'log');
  render(<EBookManagementPage />);

  const exportButton = await screen.findByLabelText('export-book-1');
  await userEvent.click(exportButton);

  expect(consoleSpy).toHaveBeenCalledWith('Exporting book:', {
    id: 1,
    title: 'React 入门指南',
    author: '张三',
    createdAt: '2023-10-01',
  });
  consoleSpy.mockRestore();
});