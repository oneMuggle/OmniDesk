import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import {
  ADMIN_ENTRY_PERMISSIONS,
  ADMIN_INDEX_CANDIDATES,
  ADMIN_ROUTE_PERMISSIONS,
  canAccessAdminPath,
  getAdminRoutePermissions,
  requiredForAdminRoute,
} from '../adminRoutePermissions';
import AdminIndexRedirect from '../../components/AdminIndexRedirect';
import ProtectedRoute from '../../../auth/components/ProtectedRoute';
import { useAuth } from '../../../auth/context/AuthContext';
import router from '../../../../routes';

jest.mock('../../../auth/context/AuthContext', () => ({
  __esModule: true,
  useAuth: jest.fn(),
}));

// 与 AuthContext.hasPermission 一致:superuser 全放行,其余 any-of
const makeHasPermission = ({ permissions = [], isSuperuser = false } = {}) => (required) => {
  if (isSuperuser) return true;
  if (!required || required.length === 0) return true;
  return [].concat(required).some((p) => permissions.includes(p));
};

const mockAuth = (opts) => {
  useAuth.mockReturnValue({
    isInitializing: false,
    isAuthenticated: true,
    hasPermission: makeHasPermission(opts),
  });
};

describe('adminRoutePermissions config', () => {
  it('every candidate and entry permission is consistent', () => {
    ADMIN_INDEX_CANDIDATES.forEach((p) => {
      expect(ADMIN_ROUTE_PERMISSIONS[p]).toBeDefined();
    });
    expect(ADMIN_ENTRY_PERMISSIONS).toEqual(expect.arrayContaining(['admin', 'manager']));
    expect(ADMIN_ENTRY_PERMISSIONS).toContain('sensor_management.view_sensor');
    expect(ADMIN_ENTRY_PERMISSIONS).not.toContain('sensors.view_sensor');
  });

  it('unknown routes default to admin only (fail closed)', () => {
    expect(getAdminRoutePermissions('does-not-exist')).toEqual(['admin']);
  });

  it('requiredForAdminRoute appends the page path for group page grants', () => {
    expect(requiredForAdminRoute('users')).toEqual([
      'admin',
      'users.view_customuser',
      '/control-panel/users',
    ]);
  });

  it('control-panel routes in the router all declare explicit permissions', () => {
    const controlPanel = router.routes.find((r) => r.path === '/control-panel');
    // 用解构读取子路由,避免 testing-library/no-node-access 误报(这里是路由配置而非 DOM)
    const collect = (routes, prefix = '') =>
      routes.flatMap((route) => {
        const { path, children: nested } = route;
        const full = path ? `${prefix}${prefix ? '/' : ''}${path}` : prefix;
        return [{ full, route, leaf: !nested }, ...(nested ? collect(nested, full) : [])];
      });
    const { children: shellChildren } = controlPanel;
    const pages = collect(shellChildren).filter(({ route, leaf }) => route.path && leaf);
    expect(pages.length).toBeGreaterThan(25);
    pages.forEach(({ full, route }) => {
      expect(route.element.type).toBe(ProtectedRoute);
      expect(route.element.props.permissions).toBeTruthy();
      const key = full.startsWith('sensors') ? 'sensors' : full;
      expect(route.element.props.permissions).toEqual(getAdminRoutePermissions(key));
    });
    expect(controlPanel.element.props.permissions).toEqual(ADMIN_ENTRY_PERMISSIONS);
  });
});

describe('canAccessAdminPath', () => {
  const plain = makeHasPermission({ permissions: [] });
  const personnelViewer = makeHasPermission({ permissions: ['personnel.view_personnel'] });

  it('non control-panel paths are always reachable', () => {
    expect(canAccessAdminPath('/memos', plain)).toBe(true);
    expect(canAccessAdminPath('/me/personnel', plain)).toBe(true);
  });

  it('matches parameterised routes and strips query strings', () => {
    expect(canAccessAdminPath('/control-panel/personnel/12', personnelViewer)).toBe(true);
    expect(canAccessAdminPath('/control-panel/personnel/12/edit', personnelViewer)).toBe(false);
    expect(canAccessAdminPath('/control-panel/personnel/add', personnelViewer)).toBe(false);
    expect(canAccessAdminPath('/control-panel/compliance?project_id=1', plain)).toBe(false);
    expect(canAccessAdminPath('/control-panel/projects', makeHasPermission({ permissions: ['admin'] }))).toBe(true);
  });

  it('sensor sub pages share the sensor permission', () => {
    const sensorViewer = makeHasPermission({ permissions: ['sensor_management.view_sensor'] });
    expect(canAccessAdminPath('/control-panel/sensors/5/calibration/history', sensorViewer)).toBe(true);
    expect(canAccessAdminPath('/control-panel/sensors/list', plain)).toBe(false);
  });

  it('rejects non-string input', () => {
    expect(canAccessAdminPath(undefined, plain)).toBe(false);
  });
});

describe('AdminIndexRedirect', () => {
  const renderIndex = () =>
    render(
      <MemoryRouter initialEntries={['/control-panel']}>
        <Routes>
          <Route path="/control-panel" element={<AdminIndexRedirect />} />
          <Route path="/control-panel/*" element={<div data-testid="landing" />} />
          <Route path="/unauthorized" element={<div>Unauthorized Page</div>} />
        </Routes>
      </MemoryRouter>
    );

  const landing = () => screen.getByTestId('landing');

  it('sends admin to the first menu page', () => {
    mockAuth({ permissions: ['admin'] });
    render(
      <MemoryRouter initialEntries={['/control-panel']}>
        <Routes>
          <Route path="/control-panel" element={<AdminIndexRedirect />} />
          <Route path="/control-panel/personnel" element={<div>Personnel Landing</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('Personnel Landing')).toBeInTheDocument();
  });

  it('sends a manager without codenames to the first page they can open', () => {
    mockAuth({ permissions: ['manager'] });
    render(
      <MemoryRouter initialEntries={['/control-panel']}>
        <Routes>
          <Route path="/control-panel" element={<AdminIndexRedirect />} />
          <Route path="/control-panel/external-links" element={<div>External Links Landing</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('External Links Landing')).toBeInTheDocument();
  });

  it('honours group page permissions', () => {
    mockAuth({ permissions: ['/control-panel/schedule/holiday'] });
    render(
      <MemoryRouter initialEntries={['/control-panel']}>
        <Routes>
          <Route path="/control-panel" element={<AdminIndexRedirect />} />
          <Route path="/control-panel/schedule/holiday" element={<div>Holiday Landing</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('Holiday Landing')).toBeInTheDocument();
  });

  it('sends users without any admin permission to /unauthorized', () => {
    mockAuth({ permissions: ['memos.view_memo'] });
    renderIndex();
    expect(screen.getByText('Unauthorized Page')).toBeInTheDocument();
    expect(screen.queryByTestId('landing')).not.toBeInTheDocument();
  });

  it('superuser lands on personnel', () => {
    mockAuth({ isSuperuser: true });
    renderIndex();
    expect(landing()).toBeInTheDocument();
  });
});

describe('control-panel guard with ProtectedRoute', () => {
  const renderGuard = (routePath, url) =>
    render(
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route
            path="*"
            element={
              <ProtectedRoute
                pagePath={`/control-panel/${routePath}`}
                permissions={getAdminRoutePermissions(routePath)}
              >
                <div>Admin Page</div>
              </ProtectedRoute>
            }
          />
          <Route path="/unauthorized" element={<div>Unauthorized Page</div>} />
        </Routes>
      </MemoryRouter>
    );

  it.each([
    ['superuser', { isSuperuser: true }, true],
    ['staff (admin)', { permissions: ['admin'] }, true],
    ['group codename', { permissions: ['users.view_customuser'] }, true],
    ['group page permission', { permissions: ['/control-panel/users'] }, true],
    ['manager without codename', { permissions: ['manager'] }, false],
    ['plain user', { permissions: [] }, false],
  ])('%s -> allowed=%s', (_label, opts, allowed) => {
    mockAuth(opts);
    renderGuard('users', '/control-panel/users');
    if (allowed) {
      expect(screen.getByText('Admin Page')).toBeInTheDocument();
    } else {
      expect(screen.getByText('Unauthorized Page')).toBeInTheDocument();
    }
  });

  it('guest is sent to login', () => {
    useAuth.mockReturnValue({
      isInitializing: false,
      isAuthenticated: false,
      hasPermission: () => false,
    });
    render(
      <MemoryRouter initialEntries={['/control-panel/users']}>
        <Routes>
          <Route
            path="/control-panel/users"
            element={
              <ProtectedRoute permissions={getAdminRoutePermissions('users')}>
                <div>Admin Page</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('Login Page')).toBeInTheDocument();
  });
});
