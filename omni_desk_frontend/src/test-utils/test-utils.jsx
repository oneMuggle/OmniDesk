import PropTypes from 'prop-types';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

/**
 * Wraps components with providers needed for testing:
 * - MemoryRouter (with optional initialEntries)
 * - QueryClientProvider
 */
export function TestWrapper({ children, initialEntries }) {
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        {children}
      </MemoryRouter>
    </QueryClientProvider>
  );
}

TestWrapper.propTypes = {
  children: PropTypes.node.isRequired,
  initialEntries: PropTypes.arrayOf(PropTypes.string),
};

/**
 * Creates a custom wrapper for render() calls.
 * Usage: render(<MyComponent />, { wrapper: renderWithProviders({ initialEntries: ['/test'] }) })
 */
export function renderWithProviders(options = {}) {
  return function Wrapper({ children }) {
    return (
      <TestWrapper initialEntries={options.initialEntries}>
        {children}
      </TestWrapper>
    );
  };
}
