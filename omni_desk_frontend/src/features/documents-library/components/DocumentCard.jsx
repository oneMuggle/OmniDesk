import { Card, Button, Space, Typography } from 'antd';
import { DownloadOutlined, EyeOutlined, ExportOutlined, FileTextOutlined } from '@ant-design/icons';
import SyncStatusBadge from './SyncStatusBadge';

const SOURCE_LABEL = {
  project_document: '项目文档',
  contract: '合同',
  policy: '制度文件',
  compliance_report: '合规报告',
  personnel_file: '人事档案',
};

export default function DocumentCard({ binding, onPreview, onDownload, onOpenInPaperless }) {
  return (
    <Card
      size="small"
      title={
        <Space>
          <FileTextOutlined />
          <Typography.Text>{binding.title}</Typography.Text>
          <SyncStatusBadge status={binding.outbox_status || 'synced'} />
        </Space>
      }
      extra={
        <Space>
          <Button icon={<EyeOutlined />} size="small" onClick={() => onPreview?.(binding)}>预览</Button>
          <Button icon={<DownloadOutlined />} size="small" onClick={() => onDownload?.(binding)}>下载</Button>
          <Button icon={<ExportOutlined />} size="small" onClick={() => onOpenInPaperless?.(binding)}>paperless 打开</Button>
        </Space>
      }
    >
      <Space direction="vertical" size={2}>
        <span>来源: {SOURCE_LABEL[binding.source_type] || binding.source_type}</span>
        <span>上传: {binding.owner_name || binding.owner}</span>
        <span>时间: {new Date(binding.created_at).toLocaleString('zh-CN')}</span>
      </Space>
    </Card>
  );
}
