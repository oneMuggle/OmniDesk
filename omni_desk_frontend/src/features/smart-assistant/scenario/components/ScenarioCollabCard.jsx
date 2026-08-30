// 多智能体协作卡片（消息流内嵌）
// 由 MessageList 在 type='collab_card' 的 assistant 消息里渲染：
// 接收 scenarioId + userInput 后,前端剧本化推进多 Agent 思考 / 工具调用 / 工具结果,
// 配对展示协作流 + 审计时间线,支持暂停/继续/重置与审计 JSON 导出。
import { useCallback, useMemo } from 'react';
import { App, Button, Card, Space, Tag, Typography, theme } from 'antd';
import {
  DownloadOutlined,
  PauseOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';

import useAgentTaskStream from '../../hooks/useAgentTaskStream';
import { getScenario } from '../data/scenarios';
import AgentCollabStream from './AgentCollabStream';
import AuditTimeline from './AuditTimeline';
import './ScenarioCollabCard.css';

const { Text, Title } = Typography;
const { useToken } = theme;

export default function ScenarioCollabCard({ scenarioId, userInput, taskId, objective }) {
  const { message } = App.useApp();
  const stream = useAgentTaskStream(taskId);

  const scenario = useMemo(() => getScenario(scenarioId), [scenarioId]);

  const exportAuditJson = useCallback(() => {
    if (!scenario && stream.events.length === 0) return;
    const payload = {
      scenarioId: scenarioId || null,
      scenarioTitle: scenario?.title || objective || '多智能体协作',
      userInput,
      status: stream.status,
      generatedAt: new Date().toISOString(),
      events: stream.events,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit-${scenarioId}-${dayjs().format('YYYYMMDD-HHmmss')}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    message.success('审计日志已下载');
  }, [scenario, scenarioId, userInput, stream.status, stream.events, message]);

  const statusTag = useMemo(() => {
    if (stream.status === 'running') return { color: 'processing', label: '协作进行中' };
    if (stream.status === 'paused') return { color: 'warning', label: '已暂停' };
    if (stream.status === 'completed') return { color: 'success', label: '已完成' };
    if (stream.status === 'failed') return { color: 'error', label: '已失败' };
    if (stream.status === 'cancelled') return { color: 'default', label: '已取消' };
    return { color: 'default', label: '准备中' };
  }, [stream.status]);

  return (
    <Card
      size="small"
      className="collab-card"
      styles={{ body: { padding: 12 } }}
      title={
        <Space size={8} wrap>
          <Text strong>{scenario?.title || objective || '多智能体协作'}</Text>
          <Tag bordered={false} color={statusTag.color}>{statusTag.label}</Tag>
          {userInput && (
            <Text type="secondary" style={{ fontSize: 12 }}>· {userInput}</Text>
          )}
        </Space>
      }
      extra={
        <Space size={4}>
          {stream.status === 'running' && (
            <Button
              size="small"
              type="text"
              icon={<PauseOutlined />}
              onClick={stream.pause}
            >
              暂停
            </Button>
          )}
          {stream.status === 'paused' && (
            <Button
              size="small"
              type="text"
              icon={<PlayCircleOutlined />}
              onClick={stream.resume}
            >
              继续
            </Button>
          )}
          <Button
            size="small"
            type="text"
            icon={<DownloadOutlined />}
            disabled={stream.events.length === 0}
            onClick={exportAuditJson}
          >
            审计
          </Button>
          <Button
            size="small"
            type="text"
            danger
            icon={<ReloadOutlined />}
            disabled={stream.events.length === 0}
            onClick={stream.retry}
          >
            重置
          </Button>
        </Space>
      }
    >
      <div className="collab-card-body">
        <div className="collab-card-stream">
          <AgentCollabStream
            events={stream.events}
            isRunning={stream.status === 'running'}
            isCompleted={stream.status === 'completed'}
            status={stream.status}
          />
        </div>
        <div className="collab-card-timeline">
          <Title level={5} style={{ margin: '4px 0 8px' }}>审计</Title>
          <AuditTimeline events={stream.events} activeScenarioId={scenarioId} />
        </div>
      </div>
    </Card>
  );
}
