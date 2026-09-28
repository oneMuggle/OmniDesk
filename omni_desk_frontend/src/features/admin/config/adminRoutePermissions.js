import { matchPath } from 'react-router-dom';

/**
 * 管理中心(/control-panel/*)路由权限:单一数据源。
 *
 * - 路由守卫(routes/index.jsx 的 ProtectedRoute permissions)、管理中心菜单
 *   (AdminLayout)、首页跳转(AdminIndexRedirect)、联邦搜索结果的可达性判断
 *   都从这里取值,保证"菜单能看到 = 路由能进 = 搜索结果能点"。
 * - 用户满足列表中任意一项即可访问(any-of)。另外,ProtectedRoute 会把
 *   该路由的 pagePath 追加为可选项,兼容用户组的页面授权(PageRoute.path)。
 * - 'admin' 由后端为 staff / superuser 下发;'manager' 为 Manager 组;
 *   其余为 Django 权限码 app_label.codename(见 users/serializers.py)。
 * - 前端权限仅负责体验与纵深防御,数据安全以后端 API 鉴权为准。
 */

export const ADMIN_ONLY = Object.freeze(['admin']);
export const ADMIN_OR_MANAGER = Object.freeze(['admin', 'manager']);

const withAdmin = (...codes) => Object.freeze(['admin', ...codes]);

/** S2-2 并入「AI 管理」的旧页面路径(用户组页面授权里可能存有这些值)。 */
const LEGACY_AI_PAGE_GRANTS = Object.freeze([
  '/smart-assistant/stats',
  '/control-panel/smart-assistant/audit',
  '/control-panel/ai-apps',
]);

/** key 为相对 /control-panel 的路由模式(与 routes/index.jsx 中的 path 一致)。 */
export const ADMIN_ROUTE_PERMISSIONS = Object.freeze({
  personnel: withAdmin('personnel.view_personnel'),
  'personnel/add': withAdmin('personnel.add_personnel'),
  'personnel/:personnelId': withAdmin('personnel.view_personnel'),
  'personnel/:personnelId/edit': withAdmin('personnel.change_personnel'),
  documents: withAdmin('documents.view_documenttemplate'),
  compliance: withAdmin('compliance.view_complianceissue'),
  'announcements/manage': withAdmin('events.view_announcement'),
  'announcements/create': withAdmin('events.add_announcement'),
  'announcements/:announcementId/edit': withAdmin('events.change_announcement'),
  schedule: withAdmin('events.view_schedule'),
  'schedule/settings': withAdmin('events.view_personnelsequence'),
  'schedule/holiday': withAdmin('events.view_holiday'),
  projects: ADMIN_ONLY,
  'meeting-rooms': withAdmin('meeting_rooms.view_meetingroom'),
  users: withAdmin('users.view_customuser'),
  // sensors/* 下所有子页面共用
  sensors: withAdmin('sensor_management.view_sensor'),
  ebooks: withAdmin('documents.view_ebook'),
  'external-links/manage': ADMIN_ONLY,
  'news/stats': ADMIN_ONLY,
  // 旧地址(S2-2 起重定向到 ai/*),保留以兼容已有的用户组页面授权
  'smart-assistant/audit': ADMIN_ONLY,
  'system-update': ADMIN_ONLY,
  'ai-apps': ADMIN_ONLY,
  // S2-2「AI 管理」:同时接受旧页面路径的用户组授权,迁移后已授权的人不会失去访问
  ai: withAdmin(...LEGACY_AI_PAGE_GRANTS),
  'ai/stats': withAdmin('/smart-assistant/stats'),
  'ai/audit': withAdmin('/control-panel/smart-assistant/audit'),
  'ai/apps': withAdmin('/control-panel/ai-apps'),
  // S4-1 数字员工:仅管理员(后端再校验超级用户 / Admin 组)
  'ai/staff': ADMIN_ONLY,
  'external-links': ADMIN_OR_MANAGER,
  'integration-hub': ADMIN_OR_MANAGER,
  'integration-hub/manage': ADMIN_ONLY,
  'plugin-market': ADMIN_OR_MANAGER,
  'plugin-market/manage': ADMIN_ONLY,
});

/** 取某个管理中心路由所需权限;未登记的路由默认仅管理员(失败时关闭)。 */
export const getAdminRoutePermissions = (routePath) =>
  ADMIN_ROUTE_PERMISSIONS[routePath] || ADMIN_ONLY;

/** 进入 /control-panel 外壳所需权限:任一子页面的权限即可。 */
export const ADMIN_ENTRY_PERMISSIONS = Object.freeze(
  Array.from(new Set(Object.values(ADMIN_ROUTE_PERMISSIONS).flat()))
);

/** 管理中心首页的候选落地页(与 AdminLayout 菜单顺序一致)。 */
export const ADMIN_INDEX_CANDIDATES = Object.freeze([
  'personnel',
  'documents',
  'schedule',
  'users',
  'sensors',
  'ebooks',
  'announcements/manage',
  'schedule/settings',
  'meeting-rooms',
  'schedule/holiday',
  'projects',
  'ai',
  'system-update',
  'external-links',
  'integration-hub',
  'plugin-market',
]);

const PREFIX = '/control-panel';

/** 路由守卫实际使用的"任意一项"权限列表(含 pagePath 形式的页面授权)。 */
export const requiredForAdminRoute = (routePath) => [
  ...getAdminRoutePermissions(routePath),
  `${PREFIX}/${routePath}`,
];

/**
 * 判断当前用户能否访问某个 /control-panel 下的具体地址(如搜索结果链接)。
 * 非管理中心地址一律返回 true(由各自页面守卫处理)。
 */
export const canAccessAdminPath = (pathname, hasPermission) => {
  if (typeof pathname !== 'string') return false;
  const path = pathname.split(/[?#]/)[0];
  if (path !== PREFIX && !path.startsWith(`${PREFIX}/`)) return true;
  if (path === PREFIX || path === `${PREFIX}/`) {
    return hasPermission([...ADMIN_ENTRY_PERMISSIONS]);
  }
  const relative = path.slice(PREFIX.length + 1);
  if (relative === 'sensors' || relative.startsWith('sensors/')) {
    return hasPermission(requiredForAdminRoute('sensors'));
  }
  const matched = Object.keys(ADMIN_ROUTE_PERMISSIONS).find((pattern) =>
    matchPath({ path: `${PREFIX}/${pattern}`, end: true }, path)
  );
  return hasPermission(requiredForAdminRoute(matched || relative));
};
