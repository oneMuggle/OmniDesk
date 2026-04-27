import PropTypes from 'prop-types';
import { Outlet } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import './App.css';
import './shared/styles/global.css';
import './shared/theme/tokens.css';
import 'react-toastify/dist/ReactToastify.css';
import ErrorBoundary from './shared/components/ErrorBoundary';
import 'animate.css';
import { AuthProvider } from './features/auth/context/AuthContext';
import { ApiProvider } from './shared/context/ApiProvider';
import { ToastContainer } from 'react-toastify';
import { RefreshProvider } from './shared/context/RefreshContext';
import { ThemeProvider, useTheme } from './shared/context/ThemeContext';
import { getAntdThemeToken } from './shared/theme/themeSchemes';

ThemeAwareConfigProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

function ThemeAwareConfigProvider({ children }) {
  const { scheme } = useTheme();
  const theme = {
    token: {
      ...getAntdThemeToken(scheme),
      colorSuccess: '#52c41a',
      colorError: '#f5222d',
      colorWarning: '#faad14',
      borderRadius: 8,
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    },
  };

  return <ConfigProvider theme={theme}>{children}</ConfigProvider>;
}

/**
 * Admin app layout — same providers as App but without the main sidebar.
 * Used as the top-level route for /control-panel.
 */
function AdminAppWrapper() {
  return (
    <ThemeProvider>
      <ThemeAwareConfigProvider>
        <AuthProvider>
          <ApiProvider>
            <RefreshProvider>
              <div className="admin-app-container">
                <ErrorBoundary>
                  <Outlet />
                </ErrorBoundary>
                <ToastContainer
                  position="top-right"
                  autoClose={5000}
                  hideProgressBar={false}
                  newestOnTop={false}
                  closeOnClick
                  rtl={false}
                  pauseOnFocusLoss
                  draggable
                  pauseOnHover
                />
              </div>
            </RefreshProvider>
          </ApiProvider>
        </AuthProvider>
      </ThemeAwareConfigProvider>
    </ThemeProvider>
  );
}

export default AdminAppWrapper;
