import React from 'react';
import { Outlet } from 'react-router-dom';
import './App.css';
import 'react-toastify/dist/ReactToastify.css';
import Sidebar from './components/Sidebar';
import 'animate.css';
import { AuthProvider } from './context/AuthContext';
import { ApiProvider } from './context/ApiProvider';
import { ToastContainer } from 'react-toastify';
import { RefreshProvider } from './context/RefreshContext';

function App() {
  return (
    <AuthProvider>
      <ApiProvider>
        <RefreshProvider>
          <div className="app-container">
          <Sidebar />
          <div className="main-content">
            <div className="content-wrapper">
              <Outlet />
            </div>
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
          </div>
        </RefreshProvider>
      </ApiProvider>
    </AuthProvider>
  );
}

export default App;
