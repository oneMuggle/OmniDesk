import { createBrowserRouter, Navigate } from 'react-router-dom';
import ProtectedRoute from '../features/auth/components/ProtectedRoute';
import GuestRoute from '../features/auth/components/GuestRoute';
import App from '../App';
import AdminAppWrapper from '../AdminAppWrapper';
import LazyComponent from './LazyComponent';
import {
  AccountBindingPage,
  AddCalibrationRecordPage,
  AdminLayout,
  AgentAuditPanel,
  AgentTaskPanel,
  AiAppManagementPage,
  AIShowcasePage,
  AnnouncementForm,
  AnnouncementsPage,
  BookPage,
  BookReaderPage,
  ChapterEditorPage,
  CommunicationPage,
  CompliancePage,
  DashboardPage,
  DifyAppList,
  DifyAppViewer,
  DocsPage,
  DocumentLibraryPage,
  DocumentsPage,
  DocumentUploadPage,
  EBookManagementPage,
  EquipmentPage,
  EventsPage,
  ExternalLinkManagementPage,
  ExternalLinksPage,
  FileAnalysisPage,
  HolidayManagementPage,
  IntegrationHubPage,
  IntegrationManagementPage,
  KnowledgeBasePage,
  LibraryPage,
  Login,
  ManageAnnouncementsPage,
  MeetingRoomBookingPage,
  MeetingRoomManagementPage,
  MemoPage,
  MyPersonnelInfo,
  NewPostPage,
  NewsStatsPage,
  NotificationCenter,
  OfficeAssistant,
  PersonnelDetailPage,
  PersonnelEditPage,
  PersonnelManagementPage,
  PluginManagementPage,
  PluginMarketPage,
  PostDetailPage,
  ProfilePage,
  ProjectsPage,
  RagflowChatPage,
  Register,
  ScheduleManagementPage,
  SchedulePage,
  ScheduleSettingsPage,
  SensorArchiveLocationManagementPage,
  SensorCalibrationHistoryPage,
  SensorCalibrationManagementPage,
  SensorCategoryManagementPage,
  SensorDetailPage,
  SensorListPage,
  SensorManagementPage,
  ShiftScheduleContainer,
  SmartChatPage,
  StatsPage,
  SyncStatusPage,
  SystemSettingsPage,
  SystemUpdatePage,
  TrialScheduleContainer,
  TrialsPage,
  UnauthorizedPage,
  UserManagementPage,
} from './lazyImports';

const router = createBrowserRouter([
  // 认证相关路由 - 不使用 App 布局（无侧边栏）
  {
    path: "/login",
    element: <GuestRoute><LazyComponent component={Login} /></GuestRoute>
  },
  {
    path: "/register",
    element: <GuestRoute><LazyComponent component={Register} /></GuestRoute>
  },
  {
    path: "/unauthorized",
    element: <LazyComponent component={UnauthorizedPage} />
  },
  // 管理中心路由 - 使用独立 AdminAppWrapper 布局（无主侧边栏，全屏显示）
  {
    path: "/control-panel",
    element: (
      <ProtectedRoute pageName="控制面板"><AdminAppWrapper /></ProtectedRoute>
    ),
    children: [
      {
        element: <AdminLayout />,
        children: [
          {
            index: true,
            element: <Navigate to="personnel" replace />
          },
          {
            path: "personnel",
            element: <LazyComponent component={PersonnelManagementPage} />
          },
          {
            path: "personnel/add",
            element: <LazyComponent component={PersonnelEditPage} />
          },
          {
            path: "personnel/:personnelId",
            element: <LazyComponent component={PersonnelDetailPage} />
          },
          {
            path: "personnel/:personnelId/edit",
            element: <LazyComponent component={PersonnelEditPage} />
          },
          {
            path: "documents",
            element: <LazyComponent component={DocumentsPage} />
          },
          {
            path: "compliance",
            element: <LazyComponent component={CompliancePage} />
          },
          {
            path: "announcements/manage",
            element: <LazyComponent component={ManageAnnouncementsPage} />
          },
          {
            path: "announcements/create",
            element: <LazyComponent component={AnnouncementForm} />
          },
          {
            path: "announcements/:announcementId/edit",
            element: <LazyComponent component={AnnouncementForm} />
          },
          {
            path: "schedule",
            element: <LazyComponent component={ScheduleManagementPage} />
          },
          {
            path: "schedule/settings",
            element: <LazyComponent component={ScheduleSettingsPage} />
          },
          {
            path: "schedule/holiday",
            element: <LazyComponent component={HolidayManagementPage} />
          },
          {
            path: "projects",
            element: <LazyComponent component={ProjectsPage} />
          },
          {
            path: "meeting-rooms",
            element: <LazyComponent component={MeetingRoomManagementPage} />
          },
          {
            path: "users",
            element: <LazyComponent component={UserManagementPage} />
          },
          {
            path: "sensors",
            element: <LazyComponent component={SensorManagementPage} />,
            children: [
              { index: true, element: <Navigate to="list" /> },
              {
                path: "list",
                element: <LazyComponent component={SensorListPage} />
              },
              {
                path: "categories",
                element: <LazyComponent component={SensorCategoryManagementPage} />
              },
              {
                path: "archive-locations",
                element: <LazyComponent component={SensorArchiveLocationManagementPage} />
              },
              {
                path: "calibration",
                element: <LazyComponent component={SensorCalibrationManagementPage} />
              },
              {
                path: ":sensorId",
                element: <LazyComponent component={SensorDetailPage} />
              },
              {
                path: ":sensorId/calibration/add",
                element: <LazyComponent component={AddCalibrationRecordPage} />
              },
              {
                path: ":sensorId/calibration/history",
                element: <LazyComponent component={SensorCalibrationHistoryPage} />
              },
            ]
          },
          {
            path: "ebooks",
            element: <LazyComponent component={EBookManagementPage} />
          },
          {
            path: "external-links/manage",
            element: <LazyComponent component={ExternalLinkManagementPage} />
          },
          {
            path: "news/stats",
            element: <LazyComponent component={NewsStatsPage} />
          },
          {
            path: "smart-assistant/audit",
            element: <LazyComponent component={AgentAuditPanel} />
          },
          {
            path: "system-update",
            element: <LazyComponent component={SystemUpdatePage} />
          },
          {
            path: "ai-apps",
            element: <LazyComponent component={AiAppManagementPage} />
          },
          {
            path: "external-links",
            element: <ProtectedRoute pageName="快捷外链"><LazyComponent component={ExternalLinksPage} /></ProtectedRoute>
          },
          {
            path: "integration-hub",
            element: <ProtectedRoute pageName="集成中心"><LazyComponent component={IntegrationHubPage} /></ProtectedRoute>
          },
          {
            path: "integration-hub/manage",
            element: <LazyComponent component={IntegrationManagementPage} />
          },
          {
            path: "plugin-market",
            element: <ProtectedRoute pageName="插件市场"><LazyComponent component={PluginMarketPage} /></ProtectedRoute>
          },
          {
            path: "plugin-market/manage",
            element: <LazyComponent component={PluginManagementPage} />
          }
        ]
      }
    ]
  },
  // 主应用路由 - 使用 App 布局（含侧边栏）
  {
    path: "/",
    element: <App />,
    children: [
      {
        index: true,
        element: (
          <ProtectedRoute pageName="仪表盘">
            <LazyComponent component={DashboardPage} />
          </ProtectedRoute>
        ),
      },
      {
        path: "meeting-rooms",
        element: <ProtectedRoute pageName="会议室预定"><LazyComponent component={MeetingRoomBookingPage} /></ProtectedRoute>
      },
      { path: "schedule", element: <GuestRoute><LazyComponent component={SchedulePage} /></GuestRoute> },
      { path: "trial-schedule", element: <GuestRoute><LazyComponent component={TrialScheduleContainer} /></GuestRoute> },
      { path: "shift-schedule", element: <GuestRoute><LazyComponent component={ShiftScheduleContainer} /></GuestRoute> },
      {
        path: "events",
        element: <ProtectedRoute pagePath="/events" pageName="事件管理"><LazyComponent component={EventsPage} /></ProtectedRoute>
      },
      {
        path: "equipment",
        element: <ProtectedRoute pagePath="/equipment" pageName="设备管理"><LazyComponent component={EquipmentPage} /></ProtectedRoute>
      },
      {
        path: "profile",
        element: <ProtectedRoute pagePath="/profile" pageName="个人资料"><LazyComponent component={ProfilePage} /></ProtectedRoute>
      },
      {
        path: "me/personnel",
        element: <ProtectedRoute pagePath="/me/personnel" pageName="我的信息"><LazyComponent component={MyPersonnelInfo} /></ProtectedRoute>
      },
      {
        path: "notifications",
        element: <ProtectedRoute pagePath="/notifications" pageName="通知中心"><LazyComponent component={NotificationCenter} /></ProtectedRoute>
      },
      {
        path: "library",
        element: <LazyComponent component={LibraryPage} />
      },
      {
        path: "books/:bookId",
        element: <LazyComponent component={BookPage} />
      },
      {
        path: "books/:bookId/reader",
        element: <LazyComponent component={BookReaderPage} />
      },
      {
        path: "books/:bookId/editor",
        element: <LazyComponent component={ChapterEditorPage} />
      },
      {
        path: "smart-assistant",
        element: <ProtectedRoute pageName="智能助手"><LazyComponent component={SmartChatPage} /></ProtectedRoute>
      },
      {
        path: "smart-assistant/stats",
        element: <ProtectedRoute pageName="智能助手统计"><LazyComponent component={StatsPage} /></ProtectedRoute>
      },
      {
        path: "smart-assistant/tasks",
        element: <ProtectedRoute pageName="多Agent任务"><LazyComponent component={AgentTaskPanel} /></ProtectedRoute>
      },
      {
        path: "knowledge-base",
        element: <ProtectedRoute pageName="知识库管理"><LazyComponent component={KnowledgeBasePage} /></ProtectedRoute>
      },
      {
        path: "ragflow-chat",
        element: <ProtectedRoute pageName="Ragflow聊天"><LazyComponent component={RagflowChatPage} /></ProtectedRoute>
      },
      {
        path: "ai-showcase",
        element: <ProtectedRoute pageName="AI能力展示"><LazyComponent component={AIShowcasePage} /></ProtectedRoute>
      },
      {
        path: "dify-apps",
        element: <ProtectedRoute pageName="Dify应用"><LazyComponent component={DifyAppList} /></ProtectedRoute>
      },
      {
        path: "dify-apps/:appId",
        element: <ProtectedRoute pageName="Dify应用"><LazyComponent component={DifyAppViewer} /></ProtectedRoute>
      },
      {
        path: "office-assistant",
        element: <ProtectedRoute pageName="Office助手"><LazyComponent component={OfficeAssistant} /></ProtectedRoute>
      },
      {
        path: "file-analysis",
        element: <ProtectedRoute pageName="文件分析"><LazyComponent component={FileAnalysisPage} /></ProtectedRoute>
      },
      {
        path: "memos",
        element: <ProtectedRoute pageName="备忘录"><LazyComponent component={MemoPage} /></ProtectedRoute>
      },
      {
        path: "communication",
        element: <ProtectedRoute pageName="交流"><LazyComponent component={CommunicationPage} /></ProtectedRoute>
      },
      {
        path: "communication/new",
        element: <ProtectedRoute pageName="新建帖子"><LazyComponent component={NewPostPage} /></ProtectedRoute>
      },
      {
        path: "communication/:postId",
        element: <LazyComponent component={PostDetailPage} />
      },
      {
        path: "announcements",
        element: <LazyComponent component={AnnouncementsPage} />
      },
      {
        path: "system-settings",
        element: <ProtectedRoute pageName="系统设置"><LazyComponent component={SystemSettingsPage} /></ProtectedRoute>
      },
      {
        path: "trials",
        element: <ProtectedRoute pageName="试验管理"><LazyComponent component={TrialsPage} /></ProtectedRoute>
      },
      {
        path: "docs/:docId",
        element: <LazyComponent component={DocsPage} />
      },
      // 文档库路由 (paperless-ngx 集成)
      {
        path: "documents-library",
        element: <ProtectedRoute pageName="文档库"><LazyComponent component={DocumentLibraryPage} /></ProtectedRoute>
      },
      {
        path: "documents-library/upload",
        element: <ProtectedRoute pageName="文档上传"><LazyComponent component={DocumentUploadPage} /></ProtectedRoute>
      },
      {
        path: "documents-library/sync",
        element: <ProtectedRoute pageName="同步状态"><LazyComponent component={SyncStatusPage} /></ProtectedRoute>
      },
      {
        path: "documents-library/account",
        element: <ProtectedRoute pageName="账户绑定"><LazyComponent component={AccountBindingPage} /></ProtectedRoute>
      },
      {
        path: "*",
        element: <Navigate to="/" replace />
      }
    ]
  }
]);

export default router;