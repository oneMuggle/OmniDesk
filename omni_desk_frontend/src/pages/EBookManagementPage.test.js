import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
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
  const mockOnFileUpload = jest.fn();
  render(<EBookManagementPage onFileUpload={mockOnFileUpload} />);

  const file = new File(['hello'], 'hello.md', { type: 'text/markdown' });
  const input = screen.getByTestId('file-input');

  await userEvent.upload(input, file);

  const uploadButton = screen.getByRole('button', { name: /上传/i });
  await userEvent.click(uploadButton);

  expect(mockOnFileUpload).toHaveBeenCalledWith(file);
});

test('opens the edit form with the correct book data', async () => {
  render(<EBookManagementPage />);

  await waitFor(() => {
    expect(screen.queryByText(/加载中.../i)).not.toBeInTheDocument();
  }, { timeout: 2000 });

  const editButtons = await screen.findAllByRole('button', { name: /编辑/i });
  await userEvent.click(editButtons[0]);

  const titleInput = await screen.findByLabelText(/书名:/i);
  const authorInput = await screen.findByLabelText(/作者:/i);

  expect(titleInput).toHaveValue('React 入门指南');
  expect(authorInput).toHaveValue('张三');
});

test('edits a book and updates the list', async () => {
  render(<EBookManagementPage />);

  await waitFor(() => {
    expect(screen.queryByText(/加载中.../i)).not.toBeInTheDocument();
  }, { timeout: 2000 });

  const editButtons = await screen.findAllByRole('button', { name: /编辑/i });
  await userEvent.click(editButtons[0]);

  const titleInput = await screen.findByLabelText(/书名:/i);
  const authorInput = await screen.findByLabelText(/作者:/i);

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

  await waitFor(() => {
    expect(screen.queryByText(/加载中.../i)).not.toBeInTheDocument();
  }, { timeout: 2000 });

  const searchInput = screen.getByPlaceholderText(/搜索电子书.../i);

  await userEvent.type(searchInput, 'React');
  expect(screen.getByText(/React 入门指南/i)).toBeInTheDocument();
  expect(screen.queryByText(/Vue.js 深度剖析/i)).not.toBeInTheDocument();

  await userEvent.clear(searchInput);
  await userEvent.type(searchInput, '王五');
  expect(screen.getByText(/JavaScript 高级编程/i)).toBeInTheDocument();
  expect(screen.queryByText(/React 入门指南/i)).not.toBeInTheDocument();
});

test('calls the onExport function when the export button is clicked', async () => {
  const mockOnExport = jest.fn();
  render(<EBookManagementPage onExport={mockOnExport} />);

  await waitFor(() => {
    expect(screen.queryByText(/加载中.../i)).not.toBeInTheDocument();
  }, { timeout: 2000 });

  const exportButtons = await screen.findAllByRole('button', { name: /导出/i });
  await userEvent.click(exportButtons[0]);

  expect(mockOnExport).toHaveBeenCalledWith({
    id: 1,
    title: 'React 入门指南',
    author: '张三',
    createdAt: '2023-10-01',
  });
});