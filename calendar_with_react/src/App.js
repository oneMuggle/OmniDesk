import React from 'react';
import { Outlet } from 'react-router-dom';
import './App.css';
import Sidebar from './components/Sidebar';
import 'animate.css';

function App() {
  return (
    <div className="app-container">
      <Sidebar />
      <div className="main-content">
        <div className="content-wrapper">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

export default App;
