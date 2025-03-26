import React from 'react';
import { Outlet } from 'react-router-dom';
import './App.css';
import Sidebar from './components/Sidebar';
import 'animate.css';
import { AuthProvider } from './context/AuthContext';
import { ApiProvider } from './context/ApiProvider';

function App() {
  return (
    <AuthProvider>
      <ApiProvider>
        <div className="app-container">
          <Sidebar />
          <div className="main-content">
            <div className="content-wrapper">
              <Outlet />
            </div>
          </div>
        </div>
      </ApiProvider>
    </AuthProvider>
  );
}

export default App;
