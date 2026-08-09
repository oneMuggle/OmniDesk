import { useState, useEffect, useCallback } from 'react';
import { Table, Tag, Typography, message } from 'antd';
import complianceApi from '../../../shared/api/compliance';
import { logger } from '../../../shared/utils/logger';

const { Title } = Typography;

const SEVERITY_COLOR = {
  低: 'default',
  中: 'blue',
  高: 'orange',
  紧急: 'red',
};

const STATUS_COLOR = {
  待处理: 'default',
  处理中: 'processing',
  已解决: 'success',
  已忽略: 'warning',
};

const columns = [
  { title: '所属项目', dataIndex: 'project_name', key: 'project_name', width: 160 },
  { title: '问题类型', dataIndex: 'issue_type', key: 'issue_type', width: 130 },
  { title: '问题描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '位置', dataIndex: 'location', key: 'location', width: 120, render: (v) => v || '—' },
  {
    title: '严重程度',
    dataIndex: 'severity',
    key: 'severity',
    width: 100,
    render: (severity) => <Tag color={SEVERITY_COLOR[severity]}>{severity}</Tag>,
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    width: 100,
    render: (status) => <Tag color={STATUS_COLOR[status]}>{status}</Tag>,
  },
  { title: '截止日期', dataIndex: 'due_date', key: 'due_date', width: 120, render: (v) => v || '—' },
];

/**
 * 合规问题列表页(P0-4)。
 *
 * 此前 compliance 模块仅有 ReportUploadButton 组件、无独立页面,导致侧边栏
 * "合规问题"入口(/control-panel/compliance)为断头路由(空白页)。本页复用
 * 既有 ComplianceIssueViewSet 列表 API 补齐该入口。
 */
const CompliancePage = () => {
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });

  const fetchIssues = useCallback(async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const response = await complianceApi.getAllComplianceIssues({ page, page_size: pageSize });
      const data = response.data;
      const list = Array.isArray(data) ? data : data.results || [];
      setIssues(list);
      setPagination((prev) => ({ ...prev, current: page, pageSize, total: data.count ?? list.length }));
    } catch (error) {
      logger.error('获取合规问题失败:', error);
      message.error('获取合规问题失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIssues(1, 10);
  }, [fetchIssues]);

  const handleTableChange = (pag) => {
    fetchIssues(pag.current, pag.pageSize);
  };

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>合规问题</Title>
      <Table
        rowKey="id"
        columns={columns}
        dataSource={issues}
        loading={loading}
        pagination={pagination}
        onChange={handleTableChange}
      />
    </div>
  );
};

export default CompliancePage;
