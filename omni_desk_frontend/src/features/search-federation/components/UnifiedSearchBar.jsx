import { useState, useMemo } from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import { AutoComplete, Tag, Flex, Spin } from 'antd';
import { useUnifiedSearch } from '../hooks/useUnifiedSearch';
import { sanitizeHtml } from '../../../shared/utils/sanitizeHtml';
import { useAuth } from '../../auth/context/AuthContext';
import { canAccessAdminPath } from '../../admin/config/adminRoutePermissions';

export const SOURCE_COLOR = {
  paperless: 'blue',
  project: 'green',
  memo: 'gold',
  personnel: 'orange',
  compliance: 'red',
  document: 'purple',
};

export const SOURCE_LABEL = {
  paperless: '文档库',
  project: '项目',
  memo: '备忘录',
  personnel: '人员',
  compliance: '合规',
  document: '公文模板',
};

// paperless 结果的 url 是后端 API 地址,不能直接打开;统一进入站内文档库页面
const PAPERLESS_ROUTE = '/documents-library';

/** 结果对应的站内路由;无法站内打开时返回 null。 */
export const resolveResultRoute = (result) => {
  if (!result) return null;
  if (result.source === 'paperless') return PAPERLESS_ROUTE;
  if (typeof result.url === 'string' && result.url.startsWith('/') && !result.url.startsWith('/api/')) {
    return result.url;
  }
  return null;
};

/**
 * 统一联邦搜索栏。
 *
 * 结果由后端按当前用户的数据范围(SELF/DEPARTMENT/GLOBAL)过滤;
 * 前端再按管理中心路由权限判断能否跳转,无权打开的结果只展示不跳转。
 */
export default function UnifiedSearchBar({
  placeholder = '搜索项目、备忘录、人员、文档...',
  style,
}) {
  const [query, setQuery] = useState('');
  const { results, degraded, loading, search } = useUnifiedSearch();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();

  const options = useMemo(
    () =>
      results.map((r) => {
        const route = resolveResultRoute(r);
        const reachable = !!route && canAccessAdminPath(route, hasPermission);
        return {
          value: `${r.source}-${r.id}`,
          disabled: !reachable,
          route: reachable ? route : null,
          label: (
            <Flex gap="small" align="center" title={reachable ? undefined : '无权限打开该页面'}>
              <Tag color={SOURCE_COLOR[r.source] || 'default'}>
                {SOURCE_LABEL[r.source] || r.source}
              </Tag>
              {r.source === 'paperless' ? (
                <span dangerouslySetInnerHTML={{ __html: sanitizeHtml(r.title) }} />
              ) : (
                <span>{r.title}</span>
              )}
              {r.source === 'paperless' && r.highlight && (
                <span
                  style={{ color: '#999', fontSize: 12 }}
                  dangerouslySetInnerHTML={{ __html: sanitizeHtml(r.highlight) }}
                />
              )}
              {r.source !== 'paperless' && r.subtitle && (
                <span style={{ color: '#999', fontSize: 12 }}>{r.subtitle}</span>
              )}
            </Flex>
          ),
        };
      }),
    [results, hasPermission],
  );

  return (
    <div>
      <AutoComplete
        style={{ width: 360, ...style }}
        placeholder={placeholder}
        value={query}
        onChange={setQuery}
        onSearch={(v) => search(v)}
        options={options}
        notFoundContent={loading ? <Spin size="small" /> : '无结果'}
        aria-label="全局搜索"
        onSelect={(_, option) => {
          setQuery('');
          if (option.route) navigate(option.route);
        }}
      />
      {degraded && (
        <div style={{ padding: '4px 0', color: '#faad14', fontSize: 12 }}>
          文档库服务暂不可用,仅显示内部结果
        </div>
      )}
    </div>
  );
}

UnifiedSearchBar.propTypes = {
  placeholder: PropTypes.string,
  style: PropTypes.object,
};
