import { createBrowserRouter, Navigate } from 'react-router-dom';
import ProtectedRoute from '../components/ProtectedRoute';
import GuestRoute from '../components/GuestRoute';
import UnauthorizedPage from '../components/UnauthorizedPage';
import App from '../App';
import CalendarPage from '../components/CalendarPage';
import SettingsPage from '../components/SettingsPage';
import DeepSeekChatPage from '../components/DeepSeekChatPage';
import EventsPage from '../components/EventsPage'; 
import ProfilePage from '../components/ProfilePage';
import Login from '../components/Login';
import Register from '../components/Register';
import DocumentsPage from '../components/DocumentsPage';
import AnnouncementsPage from '../components/AnnouncementsPage';
import TrialsPage from '../components/TrialsPage';
import PersonnelPage from '../components/PersonnelPage';
import EquipmentPage from '../components/EquipmentPage';
import FileAnalysisPage from '../components/FileAnalysisPage';
import DocsPage from '../components/DocsPage';

const router = createBrowserRouter([
{
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Navigate to="calendar" replace /> },
      { path: "calendar", element: <GuestRoute><CalendarPage /></GuestRoute> },
      {
        path: "settings",
        element: <ProtectedRoute><SettingsPage /></ProtectedRoute>
      },
      {
        path: "events",
        element: <ProtectedRoute roles={['admin', 'manager']}><EventsPage /></ProtectedRoute>
      },
      {
        path: "trials",
        element: <ProtectedRoute roles={['admin', 'manager']}><TrialsPage /></ProtectedRoute>
      },
      {
        path: "personnel",
        element: <ProtectedRoute roles={['admin', 'manager']}><PersonnelPage /></ProtectedRoute>
      },
      {
        path: "equipment",
        element: <ProtectedRoute roles={['admin', 'manager']}><EquipmentPage /></ProtectedRoute>
      },
      {
        path: "profile",
        element: <ProtectedRoute><ProfilePage /></ProtectedRoute>
      },
      {
        path: "documents",
        element: <DocumentsPage />
      },
      {
        path: "announcements",
        element: <ProtectedRoute roles={['admin', 'manager']}><AnnouncementsPage /></ProtectedRoute>
      },
      { 
        path: "deepseek-chat", 
        element: <DeepSeekChatPage /> 
      },
      { 
        path: "file-analysis", 
        element: <FileAnalysisPage /> 
      },
      { 
        path: "docs/cdepsio6", 
        element: <DocsPage /> 
      }
    ]
  },
  {
    path: "/login",
    element: <Login />
  },
  {
    path: "/register",
    element: <Register />
  },
  {
    path: "/unauthorized",
    element: <UnauthorizedPage />
  },
], { basename: "/" });

export default router;
