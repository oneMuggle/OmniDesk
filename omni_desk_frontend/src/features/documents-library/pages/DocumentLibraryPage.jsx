/**
 * 文档库主页 (paperless-ngx 集成)
 *
 * 展示当前用户绑定的所有 paperless 文档,支持分页 + 关键字过滤。
 * 后端 `/api/paperless/documents/` 尚未实现,此处使用 stub 列表,
 * 当接口返回空或失败时展示 Empty 占位。
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Table, Input, Space, Button, message, Empty, Spin, Tooltip, Typography,
} from 'antd';
import {
  SearchOutlined, DownloadOutlined, EyeOutlined, ExportOutlined, ReloadOutlined,
} from '@ant-design/icons';
import axiosInstance from '../../../shared/api/axiosConfig';
import PaperlessHealthBanner from '../components/PaperlessHealthBanner';
import SyncStatusBadge from '../components/SyncStatusBadge';

const { Text } = Typography;

const SOURCE_LABEL = {
  project_document: '项目文档',
  contract: '合同',
  policy: '制度文件',
  compliance_report: '合规报告',
  personnel_file: '人事档案',
};

const fetchDocuments = async (params) => {
  const { data } = await axiosInstance.get('/paperless/documents/', { params });
  // 兼容分页 ({results, count}) 与纯数组两种返回
  if (Array.isArray(data)) return { results: data, count: data.length };
  if (data?.results) return data;
  return { results: [], count: 0 };
};

const handleDownload = async (record) => {
  try {
    const resp = await axiosInstance.get(
      `/paperless/documents/${record.id}/download/`,
      { responseType: 'blob' },
    );
    const url = window.URL.createObjectURL(new Blob([resp.data]));
    const a = document.createElement('a');
    a.href = url;
    a.download = record.title || `document-${record.id}`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    message.success('下载成功');
  } catch {
    message.error('下载失败');
  }
};

export default function DocumentLibraryPage() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['paperless-documents', search, page, pageSize],
    queryFn: () => fetchDocuments({ search, page, page_size: pageSize }),
    keepPreviousData: true,
  });

  const documents = data?.results || [];
  const total = data?.count || 0;

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (text) => <Text strong>{text || '—'}</Text>,
    },
    {
      title: '来源',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 120,
      render: (val) => SOURCE_LABEL[val] || val || '—',
    },
    {
      title: '上传者',
      dataIndex: 'owner_name',
      key: 'owner_name',
      width: 120,
      render: (val, record) => val || record.owner || '—',
    },
    {
      title: '同步状态',
      dataIndex: 'outbox_status',
      key: 'outbox_status',
      width: 120,
      render: (val) => <SyncStatusBadge status={val || 'synced'} />,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (val) => (val ? new Date(val).toLocaleString('zh-CN') : '—'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_, record) => (
        <Space>
          <Tooltip title="预览">
            <Button
              size="small"
              type="text"
              icon={<EyeOutlined />}
              onClick={() => message.info('预览功能开发中')}
            />
          </Tooltip>
          <Tooltip title="下载">
            <Button
              size="small"
              type="text"
              icon={<DownloadOutlined />}
              onClick={() => handleDownload(record)}
            />
          </Tooltip>
          <Tooltip title="在 paperless 中打开">
            <Button
              size="small"
              type="text"
              icon={<ExportOutlined />}
              onClick={() => {
                if (record.paperless_url) {
                  window.open(record.paperless_url, '_blank');
                } else {
                  message.info('暂无 paperless 链接');
                }
              }}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} align="center">
        <h2 style={{ margin: 0 }}>文档库</h2>
        <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
      </Space>

      <PaperlessHealthBanner />

      <div style={{ marginBottom: 16 }}>
        <Input
          placeholder="搜索文档标题"
          prefix={<SearchOutlined />}
          allowClear
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          style={{ maxWidth: 360 }}
        />
      </div>

      <Spin spinning={isLoading}>
        {documents.length === 0 && !isLoading ? (
          <Empty description="暂无文档" />
        ) : (
          <Table
            rowKey="id"
            columns={columns}
            dataSource={documents}
            pagination={{
              current: page,
              pageSize,
              total,
              showSizeChanger: true,
              showTotal: (t) => `共 ${t} 条`,
              onChange: (p, ps) => {
                setPage(p);
                if (ps !== pageSize) setPage(1);
                setPageSize(ps);
              },
            }}
          />
        )}
      </Spin>
    </div>
  );
}
