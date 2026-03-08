import React, { useContext, useEffect } from 'react';
import { render, screen } from '@testing-library/react';
import PropTypes from 'prop-types';
import { AuthProvider, AuthContext } from './AuthContext';

// Helper component to set the user state within the provider's context
const MockUserSetter = ({ user }) => {
  const { setUser } = useContext(AuthContext);
  useEffect(() => {
    // Set the user state on the provider to control the test case
    setUser(user);
  }, [user, setUser]);
  return null; // This component does not render anything
};

MockUserSetter.propTypes = {
  user: PropTypes.object,
};

// Test component that consumes the real context and displays the permission check result
const PermissionDisplay = ({ requiredPermission }) => {
  const { hasPermission } = useContext(AuthContext);
  return (
    <div>
      {hasPermission(requiredPermission) ? 'Has Permission' : 'No Permission'}
    </div>
  );
};

PermissionDisplay.propTypes = {
  requiredPermission: PropTypes.oneOfType([
    PropTypes.string,
    PropTypes.array,
  ]),
};

describe('AuthProvider - hasPermission Logic', () => {
  // Helper function to render the test component within the real AuthProvider
  // and set a specific user for the test scenario.
  const renderWithUser = (user, requiredPermission) => {
    return render(
      <AuthProvider>
        <MockUserSetter user={user} />
        <PermissionDisplay requiredPermission={requiredPermission} />
      </AuthProvider>
    );
  };

  test('should return true for superusers, regardless of required permissions', () => {
    const superUser = { is_superuser: true, permissions: [] };
    renderWithUser(superUser, 'any.permission');
    expect(screen.getByText('Has Permission')).toBeInTheDocument();
  });

  test('should return true if the user has the single required permission', () => {
    const user = { is_superuser: false, permissions: ['can_edit'] };
    renderWithUser(user, 'can_edit');
    expect(screen.getByText('Has Permission')).toBeInTheDocument();
  });

  test('should return false if the user does not have the required permission', () => {
    const user = { is_superuser: false, permissions: ['can_view'] };
    renderWithUser(user, 'can_edit');
    expect(screen.getByText('No Permission')).toBeInTheDocument();
  });

  test('should return true if no permission is required (null, undefined, or empty array)', () => {
    const user = { is_superuser: false, permissions: [] };
    
    const { rerender } = renderWithUser(user, null);
    expect(screen.getByText('Has Permission')).toBeInTheDocument();

    rerender(
        <AuthProvider>
            <MockUserSetter user={user} />
            <PermissionDisplay requiredPermission={undefined} />
        </AuthProvider>
    );
    expect(screen.getByText('Has Permission')).toBeInTheDocument();

    rerender(
        <AuthProvider>
            <MockUserSetter user={user} />
            <PermissionDisplay requiredPermission={[]} />
        </AuthProvider>
    );
    expect(screen.getByText('Has Permission')).toBeInTheDocument();
  });

  test('should return false if user has no permissions and one is required', () => {
    const user = { is_superuser: false, permissions: [] };
    renderWithUser(user, 'requires.permission');
    expect(screen.getByText('No Permission')).toBeInTheDocument();
  });

  test('should return true if user has at least one of the permissions in a required array', () => {
    const user = { is_superuser: false, permissions: ['perm_a', 'perm_b'] };
    renderWithUser(user, ['perm_c', 'perm_a']);
    expect(screen.getByText('Has Permission')).toBeInTheDocument();
  });

  test('should return false if user has none of the permissions in a required array', () => {
    const user = { is_superuser: false, permissions: ['perm_a', 'perm_b'] };
    renderWithUser(user, ['perm_c', 'perm_d']);
    expect(screen.getByText('No Permission')).toBeInTheDocument();
  });

  test('should return false if the user object is null', () => {
    renderWithUser(null, 'any.permission');
    expect(screen.getByText('No Permission')).toBeInTheDocument();
  });
});
