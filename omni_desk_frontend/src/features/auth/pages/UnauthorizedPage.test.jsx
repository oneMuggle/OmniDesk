import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import UnauthorizedPage from './UnauthorizedPage';

describe('UnauthorizedPage', () => {
  it('renders unauthorized message', () => {
    render(
      <MemoryRouter>
        <UnauthorizedPage />
      </MemoryRouter>
    );
    expect(screen.getByText('权限不足')).toBeInTheDocument();
    expect(screen.getByText('请联系管理员获取相应权限')).toBeInTheDocument();
  });
});
