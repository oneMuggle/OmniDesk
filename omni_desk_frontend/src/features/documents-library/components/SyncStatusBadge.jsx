import { Tag } from 'antd';
import {
  ClockCircleOutlined, SyncOutlined, CheckCircleOutlined,
  CloseCircleOutlined, WarningOutlined,
} from '@ant-design/icons';

const STATUS_MAP = {
  pending:  { color: 'orange',  text: '待同步',   icon: <ClockCircleOutlined /> },
  syncing:  { color: 'blue',    text: '同步中',   icon: <SyncOutlined spin /> },
  synced:   { color: 'green',   text: '已同步',   icon: <CheckCircleOutlined /> },
  failed:   { color: 'red',     text: '同步失败', icon: <CloseCircleOutlined /> },
  dead:     { color: 'red',     text: '需重试',   icon: <WarningOutlined /> },
};

export default function SyncStatusBadge({ status = 'synced' }) {
  const conf = STATUS_MAP[status] || STATUS_MAP.synced;
  return <Tag color={conf.color} icon={conf.icon}>{conf.text}</Tag>;
}
