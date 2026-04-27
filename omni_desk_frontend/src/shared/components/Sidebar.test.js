import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthContext } from '../../features/auth/context/AuthContext';
import { ThemeProvider } from '../../shared/context/ThemeContext';
import Sidebar from './Sidebar';
import complianceApi from '../../features/compliance/api/compliance';

// Mock the complianceApi module
jest.mock('../../features/compliance/api/compliance');

const mockAuthContext = {
  user: null,
  isAuthenticated: false,
  logout: jest.fn(),
  hasPermission: () => true,
  isInitializing: false,
};

const renderSidebar = (authContext = mockAuthContext) => {
  return render(
    <ThemeProvider>
      <AuthContext.Provider value={authContext}>
        <MemoryRouter>
          <Sidebar isMobileMenuOpen={false} toggleMobileMenu={() => {}} />
        </MemoryRouter>
      </AuthContext.Provider>
    </ThemeProvider>
  );
};

describe('Sidebar', () => {
  beforeEach(() => {
    complianceApi.getUnreadCount.mockClear();
  });

  it('renders the sidebar with brand', () => {
    renderSidebar();
    expect(screen.getByText(/OmniDesk/i)).toBeInTheDocument();
  });

  it('shows subtitle when not collapsed', () => {
    renderSidebar();
    expect(screen.getByText(/智能办公系统/i)).toBeInTheDocument();
  });

  it('does not call notification API when not authenticated', () => {
    renderSidebar();
    expect(complianceApi.getUnreadCount).not.toHaveBeenCalled();
  });

  it('fetches notifications when authenticated', async () => {
    complianceApi.getUnreadCount.mockResolvedValue({ data: { unread_count: 5 } });
    const authenticatedContext = {
      ...mockAuthContext,
      isAuthenticated: true,
      user: { username: 'testuser', role: 'user' },
    };
    renderSidebar(authenticatedContext);

    await waitFor(() => {
      expect(complianceApi.getUnreadCount).toHaveBeenCalledTimes(1);
    });
  });

  it('renders menu items visible', () => {
    renderSidebar();
    expect(screen.getByText(/首页/i)).toBeInTheDocument();
    expect(screen.getByText(/公告栏/i)).toBeInTheDocument();
    expect(screen.getByText(/日历/i)).toBeInTheDocument();
  });
});
