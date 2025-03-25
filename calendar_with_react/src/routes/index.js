import { createBrowserRouter, Navigate } from 'react-router-dom';
import ProtectedRoute from '../components/ProtectedRoute';
import App from '../App';
import { AuthProvider } from '../context/AuthContext';
import { ApiProvider } from '../context/ApiProvider';
import CalendarPage from '../components/CalendarPage';
import SettingsPage from '../components/SettingsPage';
import DeepSeekChatPage from '../components/DeepSeekChatPage';
import EventsPage from '../components/EventsPage'; 
import ProfilePage from '../components/ProfilePage';
import Login from '../components/Login';
import DocumentsPage from '../components/DocumentsPage';
import AnnouncementsPage from '../components/AnnouncementsPage';

const router = createBrowserRouter([
{
    path: "/",
    element: (
      <AuthProvider>
        <ApiProvider>
          <App />
        </ApiProvider>
      </AuthProvider>
    ),
    children: [
      { index: true, element: <Navigate to="calendar" replace /> },
      { path: "calendar", element: <ProtectedRoute><CalendarPage /></ProtectedRoute> },
      { path: "settings", element: <ProtectedRoute><SettingsPage /></ProtectedRoute> },
      { path: "events", element: <ProtectedRoute><EventsPage /></ProtectedRoute> },
      { path: "profile", element: <ProtectedRoute><ProfilePage /></ProtectedRoute> },
      { path: "documents", element: <ProtectedRoute><DocumentsPage /></ProtectedRoute> },
      { path: "announcements", element: <ProtectedRoute><AnnouncementsPage /></ProtectedRoute> },
      { path: "deepseek-chat", element: <ProtectedRoute><DeepSeekChatPage /></ProtectedRoute> }
    ]
  },
  {
    path: "/login",
    element: (
      <AuthProvider>
        <ApiProvider>
          <Login />
        </ApiProvider>
      </AuthProvider>
    )
  },
], { basename: "/" });

export default router;
