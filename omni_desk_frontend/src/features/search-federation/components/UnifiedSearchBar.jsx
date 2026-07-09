import { useState, useMemo } from 'react';
import { AutoComplete, Tag, Flex, Spin } from 'antd';
import { useUnifiedSearch } from '../hooks/useUnifiedSearch';

const SOURCE_COLOR = {
  paperless: 'blue',
  project: 'green',
  contract: 'cyan',
  personnel: 'orange',
};

const SOURCE_LABEL = {
  paperless: '📄 paperless 文档',
  project: '项目',
  contract: '合同',
  personnel: '人员',
};

/**
 * 统一联邦搜索栏。
 *
 * @param {{ placeholder?: string }} props
 */
export default function UnifiedSearchBar({ placeholder = '搜索项目、合同、文档...' }) {
  const [query, setQuery] = useState('');
  const { results, degraded, loading, search } = useUnifiedSearch();

  const options = useMemo(
    () =>
      results.map((r) => ({
        value: r.id,
        label: (
          <Flex gap="small" align="center">
            <Tag color={SOURCE_COLOR[r.source] || 'default'}>
              {SOURCE_LABEL[r.source] || r.source}
            </Tag>
            <span dangerouslySetInnerHTML={{ __html: r.title }} />
            {r.highlight && r.source === 'paperless' && (
              <span
                style={{ color: '#999', fontSize: 12 }}
                dangerouslySetInnerHTML={{ __html: r.highlight }}
              />
            )}
          </Flex>
        ),
        url: r.url,
      })),
    [results],
  );

  return (
    <AutoComplete
      style={{ width: 360 }}
      placeholder={placeholder}
      value={query}
      onChange={setQuery}
      onSearch={(v) => search(v)}
      options={options}
      notFoundContent={loading ? <Spin size="small" /> : '无结果'}
      onSelect={(_, option) => {
        if (option.url) window.location.href = option.url;
      }}
    >
      {degraded && (
        <div style={{ padding: 8, color: '#faad14' }}>
          ⚠️ paperless 服务暂不可用,仅显示内部结果
        </div>
      )}
    </AutoComplete>
  );
}
