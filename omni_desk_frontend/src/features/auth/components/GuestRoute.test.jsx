import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import GuestRoute from './GuestRoute';
import { useAuth } from '../context/AuthContext';

jest.mock('../context/AuthContext', () => ({
  __esModule: true,
  useAuth: jest.fn(),
}));

const mockUseAuth = useAuth;

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

describe('GuestRoute', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders children for guest users', () => {
    mockUseAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: false,
      hasPermission: () => true,
    });
    renderWithRouter(
      <GuestRoute>
        <div>Guest Content</div>
      </GuestRoute>,
      { initialEntries: ['/guest'] }
    );
    expect(screen.getByText('Guest Content')).toBeInTheDocument();
  });

  it('passes isGuest prop to child', () => {
    mockUseAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: false,
      hasPermission: () => true,
    });
    const ChildWithProp = ({ isGuest }) => (
      <div>isGuest: {String(isGuest)}</div>
    );
    renderWithRouter(
      <GuestRoute>
        <ChildWithProp />
      </GuestRoute>,
      { initialEntries: ['/guest'] }
    );
    expect(screen.getByText('isGuest: true')).toBeInTheDocument();
  });

  it('redirects to unauthorized when lacking permission', () => {
    mockUseAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: true,
      hasPermission: jest.fn(() => false),
    });
    renderWithRouter(
      <GuestRoute>
        <div>Should Not See</div>
      </GuestRoute>,
      { initialEntries: ['/guest'] }
    );
    expect(screen.getByText('Unauthorized Page')).toBeInTheDocument();
  });
});
