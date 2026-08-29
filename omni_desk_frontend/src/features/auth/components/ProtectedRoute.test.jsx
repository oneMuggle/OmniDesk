import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';
import { useAuth } from '../context/AuthContext';

jest.mock('../context/AuthContext', () => ({
  __esModule: true,
  useAuth: jest.fn(),
}));

const mockUseAuth = useAuth;

const TestChild = () => <div>Protected Content</div>;

const renderWithRouter = (ui, { initialEntries } = {}) => {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route path="/unauthorized" element={<div>Unauthorized Page</div>} />
        <Route path="*" element={ui} />
      </Routes>
    </MemoryRouter>
  );
};

describe('ProtectedRoute', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows loading state while auth is initializing', () => {
    mockUseAuth.mockReturnValue({
      isInitializing: true,
      isAuthenticated: false,
      hasPermission: () => true,
    });
    renderWithRouter(<ProtectedRoute><TestChild /></ProtectedRoute>);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('redirects to /login when not authenticated and not allowing guests', () => {
    mockUseAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: false,
      hasPermission: () => true,
    });
    renderWithRouter(
      <ProtectedRoute><TestChild /></ProtectedRoute>,
      { initialEntries: ['/protected'] }
    );
    expect(screen.getByText('Login Page')).toBeInTheDocument();
  });

  it('redirects to /unauthorized when lacking required permission', () => {
    mockUseAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: true,
      hasPermission: jest.fn(() => false),
    });
    renderWithRouter(
      <ProtectedRoute permissions="admin.manage"><TestChild /></ProtectedRoute>,
      { initialEntries: ['/protected'] }
    );
    expect(screen.getByText('Unauthorized Page')).toBeInTheDocument();
  });

  it('renders children when authenticated and has permission', () => {
    mockUseAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: true,
      hasPermission: jest.fn(() => true),
    });
    renderWithRouter(
      <ProtectedRoute><TestChild /></ProtectedRoute>,
      { initialEntries: ['/protected'] }
    );
    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  it('allows guest access when allowGuest is true', () => {
    mockUseAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: false,
      hasPermission: jest.fn(() => true),
    });
    renderWithRouter(
      <ProtectedRoute allowGuest><TestChild /></ProtectedRoute>,
      { initialEntries: ['/guest-page'] }
    );
    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  it('calls hasPermission with the correct permission argument', () => {
    const hasPermission = jest.fn(() => true);
    mockUseAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: true,
      hasPermission,
    });
    renderWithRouter(
      <ProtectedRoute permissions={['events.manage', 'documents.view']}>
        <TestChild />
      </ProtectedRoute>,
      { initialEntries: ['/protected'] }
    );
    expect(hasPermission).toHaveBeenCalledWith(['events.manage', 'documents.view']);
  });

  it('allows access when permissions is null', () => {
    mockUseAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: true,
      hasPermission: jest.fn(() => true),
    });
    renderWithRouter(
      <ProtectedRoute permissions={null}><TestChild /></ProtectedRoute>,
      { initialEntries: ['/protected'] }
    );
    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  it('uses pagePath as the permission key', () => {
    const hasPermission = jest.fn(() => true);
    mockUseAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: true,
      hasPermission,
    });

    renderWithRouter(
      <ProtectedRoute pagePath="/events" pageName="事件管理">
        <TestChild />
      </ProtectedRoute>,
      { initialEntries: ['/events'] }
    );

    expect(hasPermission).toHaveBeenCalledWith('/events');
    expect(hasPermission).not.toHaveBeenCalledWith('事件管理');
  });

  it('prefers pagePath over permissions when both are provided', () => {
    const hasPermission = jest.fn(() => true);
    mockUseAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: true,
      hasPermission,
    });

    renderWithRouter(
      <ProtectedRoute
        pagePath="/events"
        permissions="events.legacy"
        pageName="事件管理"
      >
        <TestChild />
      </ProtectedRoute>,
      { initialEntries: ['/events'] }
    );

    expect(hasPermission).toHaveBeenCalledWith('/events');
    expect(hasPermission).not.toHaveBeenCalledWith('events.legacy');
  });

  it('does not use pageName as an implicit permission key', () => {
    const hasPermission = jest.fn(() => true);
    mockUseAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: true,
      hasPermission,
    });

    renderWithRouter(
      <ProtectedRoute pageName="控制面板"><TestChild /></ProtectedRoute>,
      { initialEntries: ['/control-panel'] }
    );

    expect(hasPermission).not.toHaveBeenCalledWith('控制面板');
  });

  it('does not check permissions before redirecting an anonymous user', () => {
    const hasPermission = jest.fn(() => false);
    mockUseAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: false,
      hasPermission,
    });

    renderWithRouter(
      <ProtectedRoute pagePath="/events"><TestChild /></ProtectedRoute>,
      { initialEntries: ['/events'] }
    );

    expect(screen.getByText('Login Page')).toBeInTheDocument();
    expect(hasPermission).not.toHaveBeenCalled();
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  it('does not render children when a guest lacks the page permission', () => {
    const hasPermission = jest.fn(() => false);
    mockUseAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: false,
      hasPermission,
    });

    renderWithRouter(
      <ProtectedRoute allowGuest pagePath="/admin">
        <TestChild />
      </ProtectedRoute>,
      { initialEntries: ['/admin'] }
    );

    expect(screen.getByText('Unauthorized Page')).toBeInTheDocument();
    expect(hasPermission).toHaveBeenCalledWith('/admin');
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  // 历史误用兼容:页面路由被以 <ProtectedRoute pagePath="/control-panel/...">
  // 形式传入时,URL 串与 user.permissions 数组比对永远不匹配。
  // 已认证用户(父级 AdminLayout 已校验过 admin 权限)在此处应被放行,
  // 否则会被踢到 /unauthorized。
  it('falls back to authenticated access when pagePath looks like a URL', () => {
    const hasPermission = jest.fn(() => false);
    mockUseAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: true,
      hasPermission,
    });

    renderWithRouter(
      <ProtectedRoute pagePath="/control-panel/ai-assistant-demo">
        <TestChild />
      </ProtectedRoute>,
      { initialEntries: ['/control-panel/ai-assistant-demo'] }
    );

    expect(hasPermission).toHaveBeenCalledWith('/control-panel/ai-assistant-demo');
    expect(screen.getByText('Protected Content')).toBeInTheDocument();
    expect(screen.queryByText('Unauthorized Page')).not.toBeInTheDocument();
  });
});
