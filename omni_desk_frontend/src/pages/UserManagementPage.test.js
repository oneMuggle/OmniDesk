import React from 'react';
import { render, screen } from '@testing-library/react';
import UserManagementPage from './UserManagementPage';
import userManagementApi from '../api/userManagementApi';
import { getAllPersonnel } from '../api/personnelApi';
import { permissionsApi } from '../api/permissionsApi';
import { AuthContext } from '../context/AuthContext';

jest.mock('../api/userManagementApi');
jest.mock('../api/personnelApi');
jest.mock('../api/permissionsApi');

const mockUsers = [
  { id: 1, username: 'user1', email: 'user1@example.com', role: 'user', groups: [] },
  { id: 2, username: 'user2', email: 'user2@example.com', role: 'admin', groups: [] },
];

const mockUser = { id: 1, username: 'testuser', is_superuser: true };

const renderWithAuthProvider = (component) => {
  return render(
    <AuthContext.Provider value={{ user: mockUser, isAuthenticated: true, isGuest: false, hasPermission: () => true }}>
      {component}
    </AuthContext.Provider>
  );
};

describe('UserManagementPage', () => {
  beforeEach(() => {
    userManagementApi.getAllUsers.mockResolvedValue({ data: { results: mockUsers } });
    getAllPersonnel.mockResolvedValue([]);
    permissionsApi.getGroups.mockResolvedValue({ results: [] });
  });

  it('should render user list', async () => {
    renderWithAuthProvider(<UserManagementPage />);
    expect(await screen.findByText('user1')).toBeInTheDocument();
    expect(await screen.findByText('user2')).toBeInTheDocument();
  });
});