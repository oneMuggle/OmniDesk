import { createBrowserRouter, Navigate } from 'react-router-dom';
import ProtectedRoute from '../components/ProtectedRoute';
import GuestRoute from '../components/GuestRoute';
import UnauthorizedPage from '../components/UnauthorizedPage';
import App from '../App';
import CalendarPage from '../components/CalendarPage';
import SettingsPage from '../components/SettingsPage';
import DeepSeekChatPage from '../components/DeepSeekChatPage';
import EventsPage from '../components/EventsPage';
import AdminLayout from '../components/Admin/AdminLayout';
import ProfilePage from '../components/ProfilePage';
import Login from '../components/Login';
import Register from '../components/Register';
import DocumentsPage from '../components/DocumentsPage';
import AnnouncementsPage from '../components/AnnouncementsPage';
import EquipmentPage from '../components/EquipmentPage';
import FileAnalysisPage from '../components/FileAnalysisPage';
import DocsPage from '../components/DocsPage';
import BookPage from '../components/BookPage';
import BookReaderPage from '../components/BookReaderPage';
import LibraryPage from '../components/LibraryPage';
import BookImportPage from '../components/BookImportPage';
import ChapterEditorPage from '../components/ChapterEditorPage'; // 导入 ChapterEditorPage
import TrialsPage from '../components/TrialsPage';
import PersonnelPage from '../components/PersonnelPage';
import BookManagementPage from '../components/BookManagementPage';
import TrialCalendarPage from '../components/TrialCalendarPage';
import ShiftCalendarPage from '../components/ShiftCalendarPage';
import WelcomePage from '../pages/WelcomePage'; // 导入 WelcomePage
import MemoPage from '../pages/MemoPage'; // 导入 MemoPage
import ManageAnnouncementsPage from '../components/ManageAnnouncementsPage';
import AnnouncementForm from '../components/AnnouncementForm';

const router = createBrowserRouter([
{
    path: "/",
    element: <App />,
    children: [
      {
        index: true,
        element: (
          <ProtectedRoute> {/* 使用 ProtectedRoute 判断登录状态 */}
            <WelcomePage />
          </ProtectedRoute>
        ),
      },
      { path: "calendar", element: <GuestRoute><TrialCalendarPage /></GuestRoute> },
      { path: "trial-calendar", element: <GuestRoute><TrialCalendarPage /></GuestRoute> },
      { path: "shift-calendar", element: <GuestRoute><ShiftCalendarPage /></GuestRoute> },
      {
        path: "events",
        element: <ProtectedRoute roles={['admin', 'manager']}><EventsPage /></ProtectedRoute>
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
        path: "library", // 新增书库路由
        element: <LibraryPage />
      },
      {
        path: "books/:bookId", // 动态书籍详情路由
        element: <BookPage />
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
      },
      {
        path: "books/:bookId/:chapterId/edit", // 新增章节编辑路由
        element: <ProtectedRoute roles={['admin']}><ChapterEditorPage /></ProtectedRoute> // 只有管理员可以访问
      },
      {
        path: "memos", // 新增备忘录路由
        element: <ProtectedRoute><MemoPage /></ProtectedRoute>
      },
    ]
  },
  {
    path: "/admin",
    element: <ProtectedRoute roles={['admin', 'manager']}><AdminLayout /></ProtectedRoute>,
    children: [
      { index: true, element: <Navigate to="trials" replace /> },
      {
        path: "trials",
        element: <ProtectedRoute roles={['admin', 'manager']}><TrialsPage /></ProtectedRoute>
      },
      {
        path: "personnel",
        element: <ProtectedRoute roles={['admin', 'manager']}><PersonnelPage /></ProtectedRoute>
      },
      {
        path: "book-management",
        element: <ProtectedRoute roles={['admin', 'manager']}><BookManagementPage /></ProtectedRoute>
      },
      {
        path: "documents",
        element: <ProtectedRoute roles={['admin', 'manager']}><DocumentsPage /></ProtectedRoute>
      },
      {
        path: "equipment",
        element: <ProtectedRoute roles={['admin', 'manager']}><EquipmentPage /></ProtectedRoute>
      },
      {
        path: "settings",
        element: <ProtectedRoute><SettingsPage /></ProtectedRoute>
      },
      {
        path: "announcements",
        element: <ProtectedRoute roles={['admin', 'manager']}><ManageAnnouncementsPage /></ProtectedRoute>
      },
      {
        path: "announcements/new",
        element: <ProtectedRoute roles={['admin', 'manager']}><AnnouncementForm /></ProtectedRoute>
      },
      {
        path: "announcements/edit/:id",
        element: <ProtectedRoute roles={['admin', 'manager']}><AnnouncementForm /></ProtectedRoute>
      }
    ]
  },
  {
    path: "/read-book/:bookId", // 新增独立书籍阅读路由
    element: <BookReaderPage />
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
