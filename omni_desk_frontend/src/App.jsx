import PropTypes from 'prop-types';
import { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import './App.css';
import './shared/styles/global.css';
import './shared/theme/tokens.css';
import 'react-toastify/dist/ReactToastify.css';
import Sidebar from './shared/components/Sidebar';
import QuickAssistant from './shared/components/QuickAssistant';
import ErrorBoundary from './shared/components/ErrorBoundary';
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

  // T3: ESC 关闭移动端菜单 (a11y)
  useEffect(() => {
    if (!isMobileMenuOpen) return undefined;
    const onKeyDown = (e) => {
      if (e.key === 'Escape') setMobileMenuOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isMobileMenuOpen]);

  return (
    <ThemeProvider>
      <DemoProvider>
        <ThemeAwareConfigProvider>
          <AuthProvider>
            <ApiProvider>
              <RefreshProvider>
                <div className="app-container">
                  <a href="#main-content" className="skip-link">跳至主内容</a>
                  {isMobileMenuOpen && (
                    <div
                      className="mobile-overlay"
                      onClick={toggleMobileMenu}
                      role="button"
                      aria-label="关闭导航菜单"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          toggleMobileMenu();
                        }
                      }}
                    />
                  )}
                  <Sidebar
                    isMobileMenuOpen={isMobileMenuOpen}
                    toggleMobileMenu={toggleMobileMenu}
                  />
                  <div className="main-content" id="main-content" tabIndex={-1}>
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