import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AdminLayout from './AdminLayout';
import { useAuth } from '../../auth/context/AuthContext';

jest.mock('../../auth/context/AuthContext', () => ({
  __esModule: true,
  useAuth: jest.fn(),
}));

const mockLogout = jest.fn();
const mockHasPermission = jest.fn(() => true);

const renderWithRouter = (ui, { initialEntries } = {}) => {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="*" element={ui} />
      </Routes>
    </MemoryRouter>
  );
};

describe('AdminLayout', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockHasPermission.mockReturnValue(true);
    useAuth.mockReturnValue({
      isAuthenticated: true,
      user: { username: 'admin' },
      logout: mockLogout,
      hasPermission: mockHasPermission,
    });
  });

  it('renders the admin panel header', () => {
    renderWithRouter(<AdminLayout />);
    expect(screen.getByText('管理面板')).toBeInTheDocument();
  });

  it('renders menu items for authenticated user', () => {
    renderWithRouter(<AdminLayout />);
    expect(screen.getByText('人员管理')).toBeInTheDocument();
    expect(screen.getByText('排班管理')).toBeInTheDocument();
    expect(screen.getByText('传感器管理')).toBeInTheDocument();
  });

  it('collapses sidebar when toggle button is clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AdminLayout />);

    const toggleButton = document.querySelector('.collapse-toggle');
    await user.click(toggleButton);

    const sidebar = document.querySelector('.admin-sidebar');
    expect(sidebar).toHaveClass('collapsed');
  });

  it('shows no menu items for unauthenticated user', () => {
    useAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      logout: mockLogout,
      hasPermission: mockHasPermission,
    });
    renderWithRouter(<AdminLayout />);
    expect(screen.queryByText('人员管理')).not.toBeInTheDocument();
  });

  it('highlights active menu item based on current path', () => {
    renderWithRouter(<AdminLayout />, { initialEntries: ['/control-panel/personnel'] });
    const personnelLink = document.querySelector('a[href="/control-panel/personnel"]');
    expect(personnelLink).toHaveClass('active');
  });

  it('calls logout when logout button is clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AdminLayout />);

    const logoutButton = screen.getByText('退出登录').closest('button');
    await user.click(logoutButton);

    expect(mockLogout).toHaveBeenCalled();
  });

  it('filters menu items based on permission', () => {
    mockHasPermission.mockImplementation((perm) => perm === 'admin');
    renderWithRouter(<AdminLayout />);

    expect(screen.queryByText('人员管理')).not.toBeInTheDocument();
    expect(screen.getByText('项目管理')).toBeInTheDocument();
  });

  it('renders return to home link', () => {
    renderWithRouter(<AdminLayout />);
    const homeLink = screen.getByText('返回主页');
    expect(homeLink.closest('a')).toHaveAttribute('href', '/');
  });
});
