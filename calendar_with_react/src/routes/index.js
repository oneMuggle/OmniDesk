import { createBrowserRouter, Navigate } from 'react-router-dom';
import App from '../App';
import CalendarPage from '../components/CalendarPage';
import SettingsPage from '../components/SettingsPage';
import DeepSeekChatPage from '../components/DeepSeekChatPage';
import EventsPage from '../components/EventsPage'; 
import NotificationsPage from '../components/NotificationsPage';
import ProfilePage from '../components/ProfilePage';
import Login from '../components/Login';
import DocumentsPage from '../components/DocumentsPage';
import AnnouncementsPage from '../components/AnnouncementsPage';

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Navigate to="calendar" replace /> },
      { path: "calendar", element: <CalendarPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "events", element: <EventsPage /> },
      { path: "notifications", element: <NotificationsPage /> },
      { path: "profile", element: <ProfilePage /> },
      { path: "login", element: <Login /> },
      { path: "documents", element: <DocumentsPage /> },
      { path: "announcements", element: <AnnouncementsPage /> },
      { path: "deepseek-chat", element: <DeepSeekChatPage /> }
    ]
  },
], { basename: "/" });

export default router;
