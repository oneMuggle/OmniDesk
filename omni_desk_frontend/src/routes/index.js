import { createBrowserRouter, Navigate } from 'react-router-dom';
import ProtectedRoute from '../components/ProtectedRoute';
import GuestRoute from '../components/GuestRoute';
import UnauthorizedPage from '../components/UnauthorizedPage';
import App from '../App';
import SchedulePage from '../components/SchedulePage';
import SettingsPage from '../components/SettingsPage';
import IntelligentChatPage from '../components/IntelligentChatPage';
import RagflowChatPage from '../components/RagflowChatPage';
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
import BookManageExportPage from '../components/BookManageExportPage';
import TrialCalendarPage from '../components/TrialCalendarPage';
import ShiftCalendarPage from '../components/ShiftCalendarPage';
import WelcomePage from '../pages/WelcomePage'; // 导入 WelcomePage
import MemoPage from '../pages/MemoPage'; // 导入 MemoPage
import ManageAnnouncementsPage from '../components/ManageAnnouncementsPage';
import AnnouncementForm from '../components/AnnouncementForm';
import DifyAppList from '../components/DifyApps/DifyAppList';
import DifyAppViewer from '../components/DifyApps/DifyAppViewer';
import DifyAppManagementPage from '../components/DifyApps/DifyAppManagementPage';
import ScheduleManagementPage from '../pages/ScheduleManagementPage';
import PersonnelManagementPage from '../pages/PersonnelManagementPage';
import ScheduleSettingsPage from '../components/ScheduleSettingsPage';
import OfficeAssistant from '../components/OfficeAssistant/OfficeAssistant';
import ProjectsPage from '../pages/ProjectsPage'; // Import ProjectsPage
import CompliancePage from '../pages/CompliancePage'; // Import CompliancePage
import NotificationsPage from '../pages/NotificationsPage'; // Import NotificationsPage

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
      { path: "schedule", element: <GuestRoute><SchedulePage /></GuestRoute> },
      { path: "trial-schedule", element: <GuestRoute><SchedulePage /></GuestRoute> },
      { path: "shift-schedule", element: <GuestRoute><SchedulePage /></GuestRoute> },
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
        path: "intelligent-chat",
        element: <IntelligentChatPage />
      },
      {
        path: "ragflow-chat",
        element: <RagflowChatPage />
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
      {
        path: "dify-apps",
        element: <ProtectedRoute><DifyAppList /></ProtectedRoute>
      },
      {
        path: "dify-apps/:appId",
        element: <ProtectedRoute><DifyAppViewer /></ProtectedRoute>
      },
      {
        path: "office-assistant",
        element: <ProtectedRoute><OfficeAssistant /></ProtectedRoute>
      },
      {
        path: "projects", // Move ProjectsPage to root level
        element: <ProtectedRoute roles={['admin', 'manager']}><ProjectsPage /></ProtectedRoute>
      },
      {
        path: "notifications", // Add NotificationsPage to root level
        element: <ProtectedRoute><NotificationsPage /></ProtectedRoute>
      },
      {
        path: "documents", // 将 DocumentsPage 移动到主页面路由
        element: <ProtectedRoute roles={['admin', 'manager']}><DocumentsPage /></ProtectedRoute>
      }
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
        path: "schedules",
        element: <ProtectedRoute roles={['admin', 'manager']}><ScheduleManagementPage /></ProtectedRoute>
      },
      {
        path: "personnel-management",
        element: <ProtectedRoute roles={['admin', 'manager']}><PersonnelManagementPage /></ProtectedRoute>
      },
      {
        path: "book-import",
        element: <ProtectedRoute roles={['admin', 'manager']}><BookImportPage /></ProtectedRoute>
      },
      {
        path: "book-manage-export",
        element: <ProtectedRoute roles={['admin', 'manager']}><BookManageExportPage /></ProtectedRoute>
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
      },
      {
        path: "dify-app-management",
        element: <ProtectedRoute roles={['admin', 'manager']}><DifyAppManagementPage /></ProtectedRoute>
      },
      {
        path: "schedule-settings",
        element: <ProtectedRoute roles={['admin', 'manager']}><ScheduleSettingsPage /></ProtectedRoute>
      },
      {
        path: "compliance", // Add CompliancePage route under /admin
        element: <ProtectedRoute roles={['admin', 'manager']}><CompliancePage /></ProtectedRoute>
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
