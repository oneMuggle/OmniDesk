import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/extend-expect';
import UserManagementPage from './UserManagementPage';
import { getUsers, updateUser, deleteUser } from '../api/userManagementApi';
import { AuthProvider } from '../context/AuthContext';

jest.mock('../api/userManagementApi');

const mockUsers = [
  { id: 1, username: 'user1', email: 'user1@example.com', role: 'user' },
  { id: 2, username: 'user2', email: 'user2@example.com', role: 'admin' },
];

const renderWithAuthProvider = (component) => {
  return render(
    <AuthProvider>
      {component}
    </AuthProvider>
  );
};

describe('UserManagementPage', () => {
  beforeEach(() => {
    getUsers.mockResolvedValue({ data: mockUsers });
  });

  it('should render user list', async () => {
    renderWithAuthProvider(<UserManagementPage />);
    expect(await screen.findByText('user1')).toBeInTheDocument();
    expect(await screen.findByText('user2')).toBeInTheDocument();
  });
});