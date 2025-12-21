import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthContext } from '../../features/auth/context/AuthContext';
import Sidebar from './Sidebar';
import complianceApi from '../../features/compliance/api/compliance';

// Mock the complianceApi module
jest.mock('../../features/compliance/api/compliance');

const mockAuthContext = {
  user: null,
  isAuthenticated: false,
  logout: jest.fn(),
  hasPermission: () => false,
  isInitializing: false,
};

const renderSidebar = (authContext = mockAuthContext) => {
  return render(
    <AuthContext.Provider value={authContext}>
      <MemoryRouter>
        <Sidebar isMobileMenuOpen={false} toggleMobileMenu={() => {}} />
      </MemoryRouter>
    </AuthContext.Provider>
  );
};

describe('Sidebar', () => {
  beforeEach(() => {
    // Reset mocks before each test
    complianceApi.getUnreadCount.mockClear();
  });

  it('renders the sidebar with title', () => {
    renderSidebar();
    expect(screen.getByText(/智能办公桌面管理系统/i)).toBeInTheDocument();
  });

  it('shows login hint when not authenticated', () => {
    renderSidebar();
    expect(screen.getByText(/请登录/i)).toBeInTheDocument();
    expect(complianceApi.getUnreadCount).not.toHaveBeenCalled();
  });

  it('shows user info and fetches notifications when authenticated', async () => {
    complianceApi.getUnreadCount.mockResolvedValue({ data: { unread_count: 5 } });
    const authenticatedContext = {
      ...mockAuthContext,
      isAuthenticated: true,
      user: { role: 'user' },
    };
    renderSidebar(authenticatedContext);
    expect(screen.getByText(/已登录/i)).toBeInTheDocument();
    
    // The API call is asynchronous, so we wait for it to be called.
    await waitFor(() => {
      expect(complianceApi.getUnreadCount).toHaveBeenCalledTimes(1);
    });
  });
});