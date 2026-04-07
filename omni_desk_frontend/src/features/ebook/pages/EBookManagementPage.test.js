jest.mock('antd', () => {
  const antd = jest.requireActual('antd');
  return {
    ...antd,
    message: {
      success: jest.fn(),
      error: jest.fn(),
      info: jest.fn(),
    },
  };
});
import { render, screen, waitFor, within } from '@testing-library/react';
import EBookManagementPage from './EBookManagementPage';
import userEvent from '@testing-library/user-event';
import axios from 'axios';
import { message } from 'antd';

jest.mock('axios');

const mockBooks = [
  { id: 1, title: 'React 入门指南', author: '张三', createdAt: '2023-10-01' },
  { id: 2, title: 'Vue.js 深度剖析', author: '李四', createdAt: '2023-10-02' },
  { id: 3, title: 'JavaScript 高级编程', author: '王五', createdAt: '2023-10-03' },
];

beforeEach(() => {
  axios.get.mockResolvedValue({ data: mockBooks });
  axios.post.mockResolvedValue({
    data: { id: 4, title: 'hello', author: 'Unknown', createdAt: '2023-10-04' },
  });
  axios.put.mockImplementation(async (url, data) => {
    return Promise.resolve({ data });
  });
  axios.delete.mockResolvedValue({ status: 204 });
});

test('renders without crashing', async () => {
  render(<EBookManagementPage />);
  expect(screen.getByText(/电子书管理/i)).toBeInTheDocument();
  await waitFor(() => {
    expect(screen.getByText('React 入门指南')).toBeInTheDocument();
  });
});

test('uploads a new book and displays it in the list', async () => {
  render(<EBookManagementPage />);
  
  await screen.findByText('React 入门指南'); // Wait for initial data

  const file = new File(['hello'], 'hello.md', { type: 'text/markdown' });
  // The "导入" button is inside the FileUpload component, which might not be directly accessible by its text.
  // Let's find the input and upload to it directly. This is a more robust way.
  const fileInput = screen.getByTestId('upload-input');

  await userEvent.upload(fileInput, file);

  await screen.findByText('hello');
  await waitFor(() => {
    expect(message.success).toHaveBeenCalledWith("'hello.md' 导入成功");
  });
});

test('opens the edit form with the correct book data', async () => {
  render(<EBookManagementPage />);

  const bookTitle = await screen.findByText('React 入门指南');
  const targetRowForEdit = bookTitle.closest('tr');
  const editButton = within(targetRowForEdit).getByRole('button', { name: /编\s*辑/i });
  await userEvent.click(editButton);

  const titleInput = await screen.findByLabelText(/书名/i);
  const authorInput = await screen.findByLabelText(/作者/i);

  expect(titleInput).toHaveValue('React 入门指南');
  expect(authorInput).toHaveValue('张三');
});

test('edits a book and updates the list', async () => {
  render(<EBookManagementPage />);

  const bookTitleToEdit = await screen.findByText('React 入门指南');
  const targetRowToEdit = bookTitleToEdit.closest('tr');
  const editButtonToClick = within(targetRowToEdit).getByRole('button', { name: /编\s*辑/i });
  await userEvent.click(editButtonToClick);

  const titleInput = await screen.findByLabelText(/书名/i);
  const authorInput = await screen.findByLabelText(/作者/i);

  await userEvent.clear(titleInput);
  await userEvent.type(titleInput, 'React 高级指南');
  await userEvent.clear(authorInput);
  await userEvent.type(authorInput, '李四二世');

  const saveButton = screen.getByRole('button', { name: /保\s*存/i });
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
  const searchButton = screen.getByRole('button', { name: /搜 索/i });

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


test('deletes a book and removes it from the list', async () => {
  render(<EBookManagementPage />);

  const bookTitleToDelete = await screen.findByText('React 入门指南');
  const targetRowToDelete = bookTitleToDelete.closest('tr');
  const deleteButton = within(targetRowToDelete).getByRole('button', { name: /删\s*除/i });
  await userEvent.click(deleteButton);

  // Wait for the confirmation dialog and confirm
  const confirmButton = await screen.findByRole('button', { name: /确\s*定/i });
  await userEvent.click(confirmButton);

  await waitFor(() => {
    expect(screen.queryByText('React 入门指南')).not.toBeInTheDocument();
  });

  expect(axios.delete).toHaveBeenCalledWith('/api/ebooks/1');
});