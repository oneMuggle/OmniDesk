import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

describe('DifyAppList', () => {
  it('should render when imported', async () => {
    const { default: DifyAppList } = await import('./DifyAppList');
    render(<DifyAppList />);
    // Component should render without crashing
    expect(document.body).toBeInTheDocument();
  });
});
