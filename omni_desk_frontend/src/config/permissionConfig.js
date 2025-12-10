// 权限映射配置
export const PERMISSION_MAPPING = {
  // 人员管理权限组
  personnel: {
    frontend: [
      'events.view_personnel',
      'events.add_personnel',
      'events.change_personnel', 
      'events.delete_personnel'
    ],
    backend: ['view_personnel', 'add_personnel', 'change_personnel', 'delete_personnel'],
    // 添加部分权限映射
    partial: {
      'events.view_personnel': 'view_personnel',
      'events.add_personnel': 'add_personnel', 
      'events.change_personnel': 'change_personnel',
      'events.delete_personnel': 'delete_personnel'
    }
  },
  // 日历管理权限组
  schedule: {
    frontend: [
      'events.view_schedule',
      'events.add_event',
      'events.change_event',
      'events.delete_event'
    ],
    backend: 'manage_schedule'
  },
  // 日程管理权限组
  schedule: {
    frontend: [
      'events.view_schedule',
      'events.add_schedule',
      'events.change_schedule',
      'events.delete_schedule'
    ],
    backend: 'manage_schedule',
    partial: {
      'events.view_schedule': 'view_schedule',
      'events.add_schedule': 'add_schedule',
      'events.change_schedule': 'change_schedule',
      'events.delete_schedule': 'delete_schedule'
    }
  },
  // 文档管理权限组
  documents: {
    frontend: ['events.view_documents', 'events.manage_documents'],
    backend: 'manage_documents'
  },
  // 设备管理权限组
  equipment: {
    frontend: ['events.view_equipment', 'events.manage_equipment'],
    backend: 'manage_equipment'
  },
  // 人员管理权限组
  personnel: {
    frontend: ['events.view_personnel', 'events.manage_personnel'],
    backend: 'manage_personnel'
  },
  // 公告管理权限组
  announcements: {
    frontend: ['events.view_announcements', 'users.manage_announcements'],
    backend: 'users.manage_announcements'
  },
  // AI聊天权限组
  ai_chat: {
    frontend: ['events.use_ai_chat'],
    backend: 'use_ai_chat'
  },
  // 文件分析权限组
  file_analysis: {
    frontend: ['events.analyze_files'],
    backend: 'analyze_files'
  }
};

// 环境特定权限配置
export const ENV_PERMISSIONS = {
  development: {
    // 开发环境放宽权限检查
    strictMode: false
  },
  production: {
    strictMode: true
  }
};

// 权限组定义
export const PERMISSION_GROUPS = {
  BASIC_USER: {
    name: '基础用户',
    permissions: ['use_ai_chat', 'analyze_files', 'view_documents', 'view_communication']
  },
  ADMIN: {
    name: '管理员',
    permissions: ['manage_personnel', 'manage_schedule', 'system_settings']
  },
  EDITOR: {
    name: '编辑',
    permissions: ['manage_schedule']
  }
};

// 权限检查工具函数
export const checkPermission = (userPermissions, requiredPermission) => {
  // 转换权限数据格式
  let permissionsList = [];
  if (Array.isArray(userPermissions)) {
    permissionsList = userPermissions;
  } else if (userPermissions && typeof userPermissions === 'object') {
    // 处理对象格式权限
    if (userPermissions.permissions && Array.isArray(userPermissions.permissions)) {
      permissionsList = userPermissions.permissions;
    } else if (userPermissions.role === 'superuser') {
      return true; // 超级用户拥有所有权限
    } else {
      // 处理扁平化权限对象 {perm1: true, perm2: false}
      permissionsList = Object.entries(userPermissions)
        .filter(([_, value]) => value === true)
        .map(([key]) => key);
    }
  }

  // 1. 直接检查权限
  if (permissionsList.includes(requiredPermission)) {
    return true;
  }

  // 2. 检查前端权限映射
  for (const [group, mapping] of Object.entries(PERMISSION_MAPPING)) {
    if (mapping.partial && mapping.partial[requiredPermission]) {
      // 如果请求的权限是前端权限，检查映射的后端权限
      const backendPerm = mapping.partial[requiredPermission];
      if (permissionsList.includes(backendPerm)) {
        return true;
      }
    }
  }

  console.debug('权限检查:', {
    requiredPermission,
    availablePermissions: permissionsList,
    rawPermissions: userPermissions
  });

  // 3. 检查后端权限映射
  for (const [group, mapping] of Object.entries(PERMISSION_MAPPING)) {
    // 检查完整后端权限映射
    if (Array.isArray(mapping.backend)) {
      if (mapping.backend.includes(requiredPermission)) {
        return mapping.frontend.some(perm => permissionsList.includes(perm));
      }
    } else if (mapping.backend === requiredPermission) {
      return mapping.frontend.some(perm => permissionsList.includes(perm));
    }
    // 检查部分权限映射
    if (mapping.partial) {
      for (const [frontendPerm, backendPerm] of Object.entries(mapping.partial)) {
        if (backendPerm === requiredPermission && permissionsList.includes(frontendPerm)) {
          return true;
        }
      }
    }
  }

  // 3. 检查权限组
  for (const [group, config] of Object.entries(PERMISSION_GROUPS)) {
    if (config.permissions.includes(requiredPermission)) {
      return config.permissions.every(perm => permissionsList.includes(perm));
    }
  }

  return false;
};
