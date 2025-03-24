import { createBrowserRouter, Navigate } from 'react-router-dom';
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
      { path: "calendar", element: <CalendarPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "events", element: <EventsPage /> },
      { path: "profile", element: <ProfilePage /> },
      { path: "documents", element: <DocumentsPage /> },
      { path: "announcements", element: <AnnouncementsPage /> },
      { path: "deepseek-chat", element: <DeepSeekChatPage /> }
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
