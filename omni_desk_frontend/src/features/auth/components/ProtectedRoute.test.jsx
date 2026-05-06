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
});
