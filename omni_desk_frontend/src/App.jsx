import PropTypes from 'prop-types';
import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import './App.css';
import './shared/styles/global.css';
import './shared/theme/tokens.css';
import 'react-toastify/dist/ReactToastify.css';
import Sidebar from './shared/components/Sidebar';
import QuickAssistant from './shared/components/QuickAssistant';
import ErrorBoundary from './shared/components/ErrorBoundary';
import 'animate.css';
import { AuthProvider } from './features/auth/context/AuthContext';
import { ApiProvider } from './shared/context/ApiProvider';
import { ToastContainer } from 'react-toastify';
import { RefreshProvider } from './shared/context/RefreshContext';
import { ThemeProvider, useTheme } from './shared/context/ThemeContext';
import { DemoProvider } from './shared/context/DemoContext';
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

function App() {
  const [isMobileMenuOpen, setMobileMenuOpen] = useState(false);

  const toggleMobileMenu = () => {
    setMobileMenuOpen(!isMobileMenuOpen);
  };

  return (
    <ThemeProvider>
      <DemoProvider>
        <ThemeAwareConfigProvider>
          <AuthProvider>
            <ApiProvider>
              <RefreshProvider>
                <div className="app-container">
                  {isMobileMenuOpen && (
                    <div className="mobile-overlay" onClick={toggleMobileMenu} />
                  )}
                  <Sidebar
                    isMobileMenuOpen={isMobileMenuOpen}
                    toggleMobileMenu={toggleMobileMenu}
                  />
                  <div className="main-content">
                    <ErrorBoundary>
                      <div className="content-wrapper">
                        <Outlet />
                      </div>
                    </ErrorBoundary>
                  </div>
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
                  <QuickAssistant />
                </div>
              </RefreshProvider>
            </ApiProvider>
          </AuthProvider>
        </ThemeAwareConfigProvider>
      </DemoProvider>
    </ThemeProvider>
  );
}

export default App;