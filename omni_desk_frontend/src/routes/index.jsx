import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom';
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
  StudentListPage,
  StudentEditPage,
  ReportReviewPage,
  CycleManagementPage,
  StipendReviewPage,
  ExpertScoringPage,
  MyReportsPage,
  MyStipendsPage,
  MentorOverviewPage,
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
      <ProtectedRoute><AdminAppWrapper /></ProtectedRoute>
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
            element: <ProtectedRoute pagePath="/control-panel/personnel" pageName="人员管理"><LazyComponent component={PersonnelManagementPage} /></ProtectedRoute>
          },
          {
            path: "personnel/add",
            element: <ProtectedRoute pagePath="/control-panel/personnel/add" pageName="新增人员"><LazyComponent component={PersonnelEditPage} /></ProtectedRoute>
          },
          {
            path: "personnel/:personnelId",
            element: <ProtectedRoute pagePath="/control-panel/personnel/:personnelId" pageName="人员详情"><LazyComponent component={PersonnelDetailPage} /></ProtectedRoute>
          },
          {
            path: "personnel/:personnelId/edit",
            element: <ProtectedRoute pagePath="/control-panel/personnel/:personnelId/edit" pageName="编辑人员"><LazyComponent component={PersonnelEditPage} /></ProtectedRoute>
          },
          {
            path: "documents",
            element: <ProtectedRoute pagePath="/control-panel/documents" pageName="文档管理"><LazyComponent component={DocumentsPage} /></ProtectedRoute>
          },
          {
            path: "compliance",
            element: <ProtectedRoute pagePath="/control-panel/compliance" pageName="合规管理"><LazyComponent component={CompliancePage} /></ProtectedRoute>
          },
          {
            path: "announcements/manage",
            element: <ProtectedRoute pagePath="/control-panel/announcements/manage" pageName="公告管理"><LazyComponent component={ManageAnnouncementsPage} /></ProtectedRoute>
          },
          {
            path: "announcements/create",
            element: <ProtectedRoute pagePath="/control-panel/announcements/create" pageName="创建公告"><LazyComponent component={AnnouncementForm} /></ProtectedRoute>
          },
          {
            path: "announcements/:announcementId/edit",
            element: <ProtectedRoute pagePath="/control-panel/announcements/:announcementId/edit" pageName="编辑公告"><LazyComponent component={AnnouncementForm} /></ProtectedRoute>
          },
          {
            path: "schedule",
            element: <ProtectedRoute pagePath="/control-panel/schedule" pageName="排班管理"><LazyComponent component={ScheduleManagementPage} /></ProtectedRoute>
          },
          {
            path: "schedule/settings",
            element: <ProtectedRoute pagePath="/control-panel/schedule/settings" pageName="排班设置"><LazyComponent component={ScheduleSettingsPage} /></ProtectedRoute>
          },
          {
            path: "schedule/holiday",
            element: <ProtectedRoute pagePath="/control-panel/schedule/holiday" pageName="节假日管理"><LazyComponent component={HolidayManagementPage} /></ProtectedRoute>
          },
          {
            path: "projects",
            element: <ProtectedRoute pagePath="/control-panel/projects" pageName="项目管理"><LazyComponent component={ProjectsPage} /></ProtectedRoute>
          },
          {
            path: "meeting-rooms",
            element: <ProtectedRoute pagePath="/control-panel/meeting-rooms" pageName="会议室管理"><LazyComponent component={MeetingRoomManagementPage} /></ProtectedRoute>
          },
          {
            path: "users",
            element: <ProtectedRoute pagePath="/control-panel/users" pageName="用户管理"><LazyComponent component={UserManagementPage} /></ProtectedRoute>
          },
          {
            path: "sensors",
            element: <ProtectedRoute><Outlet /></ProtectedRoute>,
            children: [
              { index: true, element: <Navigate to="list" /> },
              {
                path: "list",
                element: <ProtectedRoute pagePath="/control-panel/sensors/list" pageName="传感器列表"><LazyComponent component={SensorListPage} /></ProtectedRoute>
              },
              {
                path: "categories",
                element: <ProtectedRoute pagePath="/control-panel/sensors/categories" pageName="传感器分类"><LazyComponent component={SensorCategoryManagementPage} /></ProtectedRoute>
              },
              {
                path: "archive-locations",
                element: <ProtectedRoute pagePath="/control-panel/sensors/archive-locations" pageName="传感器归档位置"><LazyComponent component={SensorArchiveLocationManagementPage} /></ProtectedRoute>
              },
              {
                path: "calibration",
                element: <ProtectedRoute pagePath="/control-panel/sensors/calibration" pageName="传感器校准"><LazyComponent component={SensorCalibrationManagementPage} /></ProtectedRoute>
              },
              {
                path: ":sensorId",
                element: <ProtectedRoute pagePath="/control-panel/sensors/:sensorId" pageName="传感器详情"><LazyComponent component={SensorDetailPage} /></ProtectedRoute>
              },
              {
                path: ":sensorId/calibration/add",
                element: <ProtectedRoute pagePath="/control-panel/sensors/:sensorId/calibration/add" pageName="新增校准记录"><LazyComponent component={AddCalibrationRecordPage} /></ProtectedRoute>
              },
              {
                path: ":sensorId/calibration/history",
                element: <ProtectedRoute pagePath="/control-panel/sensors/:sensorId/calibration/history" pageName="校准历史"><LazyComponent component={SensorCalibrationHistoryPage} /></ProtectedRoute>
              },
            ]
          },
          {
            path: "ebooks",
            element: <ProtectedRoute pagePath="/control-panel/ebooks" pageName="电子书管理"><LazyComponent component={EBookManagementPage} /></ProtectedRoute>
          },
          {
            path: "external-links/manage",
            element: <ProtectedRoute pagePath="/control-panel/external-links/manage" pageName="外链管理"><LazyComponent component={ExternalLinkManagementPage} /></ProtectedRoute>
          },
          {
            path: "news/stats",
            element: <ProtectedRoute pagePath="/control-panel/news/stats" pageName="新闻统计"><LazyComponent component={NewsStatsPage} /></ProtectedRoute>
          },
          {
            path: "smart-assistant/audit",
            element: <ProtectedRoute pagePath="/control-panel/smart-assistant/audit" pageName="智能助手审计"><LazyComponent component={AgentAuditPanel} /></ProtectedRoute>
          },
          {
            path: "system-update",
            element: <ProtectedRoute pagePath="/control-panel/system-update" pageName="系统更新"><LazyComponent component={SystemUpdatePage} /></ProtectedRoute>
          },
          {
            path: "ai-apps",
            element: <ProtectedRoute pagePath="/control-panel/ai-apps" pageName="AI 应用"><LazyComponent component={AiAppManagementPage} /></ProtectedRoute>
          },
          {
            path: "external-links",
            element: <ProtectedRoute pagePath="/control-panel/external-links" pageName="快捷外链"><LazyComponent component={ExternalLinksPage} /></ProtectedRoute>
          },
          {
            path: "integration-hub",
            element: <ProtectedRoute pagePath="/control-panel/integration-hub" pageName="集成中心"><LazyComponent component={IntegrationHubPage} /></ProtectedRoute>
          },
          {
            path: "integration-hub/manage",
            element: <ProtectedRoute pagePath="/control-panel/integration-hub/manage" pageName="集成管理"><LazyComponent component={IntegrationManagementPage} /></ProtectedRoute>
          },
          {
            path: "plugin-market",
            element: <ProtectedRoute pagePath="/control-panel/plugin-market" pageName="插件市场"><LazyComponent component={PluginMarketPage} /></ProtectedRoute>
          },
          {
            path: "plugin-market/manage",
            element: <ProtectedRoute pagePath="/control-panel/plugin-market/manage" pageName="插件管理"><LazyComponent component={PluginManagementPage} /></ProtectedRoute>
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
          <ProtectedRoute>
            <LazyComponent component={DashboardPage} />
          </ProtectedRoute>
        ),
      },
      {
        path: "meeting-rooms",
        element: <ProtectedRoute pagePath="/meeting-rooms" pageName="会议室预定"><LazyComponent component={MeetingRoomBookingPage} /></ProtectedRoute>
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
        element: <ProtectedRoute pagePath="/library" pageName="书库"><LazyComponent component={LibraryPage} /></ProtectedRoute>
      },
      {
        path: "books/:bookId",
        element: <ProtectedRoute pagePath="/books/:bookId" pageName="书籍详情"><LazyComponent component={BookPage} /></ProtectedRoute>
      },
      {
        path: "books/:bookId/reader",
        element: <ProtectedRoute pagePath="/books/:bookId/reader" pageName="书籍阅读器"><LazyComponent component={BookReaderPage} /></ProtectedRoute>
      },
      {
        path: "books/:bookId/editor",
        element: <ProtectedRoute pagePath="/books/:bookId/editor" pageName="章节编辑器"><LazyComponent component={ChapterEditorPage} /></ProtectedRoute>
      },
      {
        path: "smart-assistant",
        element: <ProtectedRoute pagePath="/smart-assistant" pageName="智能助手"><LazyComponent component={SmartChatPage} /></ProtectedRoute>
      },
      {
        path: "smart-assistant/stats",
        element: <ProtectedRoute pagePath="/smart-assistant/stats" pageName="智能助手统计"><LazyComponent component={StatsPage} /></ProtectedRoute>
      },
      {
        path: "smart-assistant/tasks",
        element: <ProtectedRoute pagePath="/smart-assistant/tasks" pageName="多Agent任务"><LazyComponent component={AgentTaskPanel} /></ProtectedRoute>
      },
      {
        path: "knowledge-base",
        element: <ProtectedRoute pagePath="/knowledge-base" pageName="知识库管理"><LazyComponent component={KnowledgeBasePage} /></ProtectedRoute>
      },
      {
        path: "ragflow-chat",
        element: <ProtectedRoute pagePath="/ragflow-chat" pageName="Ragflow聊天"><LazyComponent component={RagflowChatPage} /></ProtectedRoute>
      },
      {
        path: "ai-showcase",
        element: <ProtectedRoute pagePath="/ai-showcase" pageName="AI能力展示"><LazyComponent component={AIShowcasePage} /></ProtectedRoute>
      },
      {
        path: "dify-apps",
        element: <ProtectedRoute pagePath="/dify-apps" pageName="Dify应用"><LazyComponent component={DifyAppList} /></ProtectedRoute>
      },
      {
        path: "dify-apps/:appId",
        element: <ProtectedRoute pagePath="/dify-apps/:appId" pageName="Dify应用详情"><LazyComponent component={DifyAppViewer} /></ProtectedRoute>
      },
      {
        path: "office-assistant",
        element: <ProtectedRoute pagePath="/office-assistant" pageName="Office助手"><LazyComponent component={OfficeAssistant} /></ProtectedRoute>
      },
      {
        path: "file-analysis",
        element: <ProtectedRoute pagePath="/file-analysis" pageName="文件分析"><LazyComponent component={FileAnalysisPage} /></ProtectedRoute>
      },
      {
        path: "memos",
        element: <ProtectedRoute pagePath="/memos" pageName="备忘录"><LazyComponent component={MemoPage} /></ProtectedRoute>
      },
      {
        path: "communication",
        element: <ProtectedRoute pagePath="/communication" pageName="交流"><LazyComponent component={CommunicationPage} /></ProtectedRoute>
      },
      {
        path: "communication/new",
        element: <ProtectedRoute pagePath="/communication/new" pageName="新建帖子"><LazyComponent component={NewPostPage} /></ProtectedRoute>
      },
      {
        path: "communication/:postId",
        element: <ProtectedRoute pagePath="/communication/:postId" pageName="帖子详情"><LazyComponent component={PostDetailPage} /></ProtectedRoute>
      },
      {
        path: "announcements",
        element: <ProtectedRoute pagePath="/announcements" pageName="公告"><LazyComponent component={AnnouncementsPage} /></ProtectedRoute>
      },
      {
        path: "system-settings",
        element: <ProtectedRoute pagePath="/system-settings" pageName="系统设置"><LazyComponent component={SystemSettingsPage} /></ProtectedRoute>
      },
      {
        path: "trials",
        element: <ProtectedRoute pagePath="/trials" pageName="试验管理"><LazyComponent component={TrialsPage} /></ProtectedRoute>
      },
      {
        path: "docs/:docId",
        element: <ProtectedRoute pagePath="/docs/:docId" pageName="文档详情"><LazyComponent component={DocsPage} /></ProtectedRoute>
      },
      // 文档库路由 (paperless-ngx 集成)
      {
        path: "documents-library",
        element: <ProtectedRoute pagePath="/documents-library" pageName="文档库"><LazyComponent component={DocumentLibraryPage} /></ProtectedRoute>
      },
      {
        path: "documents-library/upload",
        element: <ProtectedRoute pagePath="/documents-library/upload" pageName="文档上传"><LazyComponent component={DocumentUploadPage} /></ProtectedRoute>
      },
      {
        path: "documents-library/sync",
        element: <ProtectedRoute pagePath="/documents-library/sync" pageName="同步状态"><LazyComponent component={SyncStatusPage} /></ProtectedRoute>
      },
      {
        path: "documents-library/account",
        element: <ProtectedRoute pagePath="/documents-library/account" pageName="账户绑定"><LazyComponent component={AccountBindingPage} /></ProtectedRoute>
      },
      // 联培生模块(4 角色 13 路由)
      {
        path: "joint-students/admin/students",
        element: <ProtectedRoute pagePath="/joint-students/admin/students" pageName="联培生管理员首页"><LazyComponent component={StudentListPage} /></ProtectedRoute>
      },
      {
        path: "joint-students/admin/students/new",
        element: <ProtectedRoute pagePath="/joint-students/admin/students/new" pageName="创建联培生"><LazyComponent component={StudentEditPage} /></ProtectedRoute>
      },
      {
        path: "joint-students/admin/students/:id",
        element: <ProtectedRoute pagePath="/joint-students/admin/students/:id" pageName="联培生详情"><LazyComponent component={StudentEditPage} /></ProtectedRoute>
      },
      {
        path: "joint-students/admin/students/:id/edit",
        element: <ProtectedRoute pagePath="/joint-students/admin/students/:id/edit" pageName="编辑联培生"><LazyComponent component={StudentEditPage} /></ProtectedRoute>
      },
      {
        path: "joint-students/admin/reports",
        element: <ProtectedRoute pagePath="/joint-students/admin/reports" pageName="报告审核"><LazyComponent component={ReportReviewPage} /></ProtectedRoute>
      },
      {
        path: "joint-students/admin/cycles",
        element: <ProtectedRoute pagePath="/joint-students/admin/cycles" pageName="批次管理"><LazyComponent component={CycleManagementPage} /></ProtectedRoute>
      },
      {
        path: "joint-students/admin/cycles/:id",
        element: <ProtectedRoute pagePath="/joint-students/admin/cycles/:id" pageName="批次详情"><LazyComponent component={CycleManagementPage} /></ProtectedRoute>
      },
      {
        path: "joint-students/admin/stipends",
        element: <ProtectedRoute pagePath="/joint-students/admin/stipends" pageName="补助复核"><LazyComponent component={StipendReviewPage} /></ProtectedRoute>
      },
      {
        path: "joint-students/expert/scoring",
        element: <ProtectedRoute pagePath="/joint-students/expert/scoring" pageName="专家打分"><LazyComponent component={ExpertScoringPage} /></ProtectedRoute>
      },
      {
        path: "joint-students/student/reports",
        element: <ProtectedRoute pagePath="/joint-students/student/reports" pageName="我的报告"><LazyComponent component={MyReportsPage} /></ProtectedRoute>
      },
      {
        path: "joint-students/student/reports/new",
        element: <ProtectedRoute pagePath="/joint-students/student/reports/new" pageName="填报报告"><LazyComponent component={MyReportsPage} /></ProtectedRoute>
      },
      {
        path: "joint-students/student/stipends",
        element: <ProtectedRoute pagePath="/joint-students/student/stipends" pageName="我的补助"><LazyComponent component={MyStipendsPage} /></ProtectedRoute>
      },
      {
        path: "joint-students/mentor/overview",
        element: <ProtectedRoute pagePath="/joint-students/mentor/overview" pageName="导师视图"><LazyComponent component={MentorOverviewPage} /></ProtectedRoute>
      },
      {
        path: "*",
        element: <Navigate to="/" replace />
      }
    ]
  }
]);

export default router;