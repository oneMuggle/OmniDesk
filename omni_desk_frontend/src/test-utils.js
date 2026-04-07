import { render } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import PropTypes from 'prop-types';

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false, // Turn off retries for tests
    },
  },
});

const AllTheProviders = ({ children }) => {
  const testQueryClient = createTestQueryClient();
  return (
    <MemoryRouter>
      <QueryClientProvider client={testQueryClient}>
        <ConfigProvider locale={zhCN}>
          {children}
        </ConfigProvider>
      </QueryClientProvider>
    </MemoryRouter>
  );
};

AllTheProviders.propTypes = {
    children: PropTypes.node.isRequired,
};


const renderWithProviders = (ui, options) =>
  render(ui, { wrapper: AllTheProviders, ...options });

// re-export everything
export * from '@testing-library/react';

// override render method
export { renderWithProviders as render };