import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

// Simple mock test for admin components that may have complex dependencies
describe('Admin Components', () => {
  it('AdminLayout should render navigation', async () => {
    const { default: AdminLayout } = await import('./AdminLayout');
    render(<AdminLayout />);
    expect(screen.getByRole('navigation')).toBeInTheDocument();
  });
});
