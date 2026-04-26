/**
 * 配色方案定义 - 所有主题的唯一数据源
 */

export const THEME_SCHEMES = {
  indigo: {
    id: 'indigo',
    name: '靛蓝紫',
    primary: '#6366f1',
    primaryHover: '#818cf8',
    primaryActive: '#4f46e5',
    primaryOutline: 'rgba(99, 102, 241, 0.2)',
    gradient: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
  },
  teal: {
    id: 'teal',
    name: '青翠绿',
    primary: '#0d9488',
    primaryHover: '#14b8a6',
    primaryActive: '#0f766e',
    primaryOutline: 'rgba(13, 148, 136, 0.2)',
    gradient: 'linear-gradient(135deg, #0d9488, #059669)',
  },
  amber: {
    id: 'amber',
    name: '琥珀橙',
    primary: '#d97706',
    primaryHover: '#f59e0b',
    primaryActive: '#b45309',
    primaryOutline: 'rgba(217, 119, 6, 0.2)',
    gradient: 'linear-gradient(135deg, #d97706, #e11d48)',
  },
  skyblue: {
    id: 'skyblue',
    name: '天蓝色',
    primary: '#0284c7',
    primaryHover: '#38bdf8',
    primaryActive: '#0369a1',
    primaryOutline: 'rgba(2, 132, 199, 0.2)',
    gradient: 'linear-gradient(135deg, #0284c7, #f43f5e)',
  },
};

export const DEFAULT_THEME = 'teal';

export const THEME_OPTIONS = Object.values(THEME_SCHEMES);

export function getSchemeById(id) {
  return THEME_SCHEMES[id] || THEME_SCHEMES[DEFAULT_THEME];
}

export function getAntdThemeToken(scheme) {
  return {
    colorPrimary: scheme.primary,
    colorPrimaryHover: scheme.primaryHover,
    colorPrimaryActive: scheme.primaryActive,
    colorPrimaryBorder: scheme.primaryOutline,
  };
}
