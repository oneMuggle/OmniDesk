import React, { useContext } from 'react';
import { render, screen } from '@testing-library/react';
import { RefreshProvider, useRefresh } from './RefreshContext';

// eslint-disable-next-line jest/no-disabled-tests
describe.skip('RefreshContext', () => {
  it('should provide refresh function', () => {
    const TestComponent = () => {
      const { refresh } = useRefresh();
      return <button onClick={refresh}>Refresh</button>;
    };

    render(
      <RefreshProvider>
        <TestComponent />
      </RefreshProvider>
    );

    expect(screen.getByText('Refresh')).toBeInTheDocument();
  });
});
