// 多智能体协作卡片（消息流内嵌）
// 由 MessageList 在 type='collab_card' 的 assistant 消息里渲染：
// 接收 scenarioId + userInput 后,前端剧本化推进多 Agent 思考 / 工具调用 / 工具结果,
// 配对展示协作流 + 审计时间线,支持暂停/继续/重置与审计 JSON 导出。
import { useCallback, useEffect, useMemo } from 'react';
import { App, Button, Card, Space, Tag, Typography, theme } from 'antd';
import {
  DownloadOutlined,
  PauseOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';

import { useScenarioPlayer } from '../hooks/useScenarioPlayer';
import { getScenario } from '../data/scenarios';
import AgentCollabStream from './AgentCollabStream';
import AuditTimeline from './AuditTimeline';
import './ScenarioCollabCard.css';

const { Text, Title } = Typography;
const { useToken } = theme;

export default function ScenarioCollabCard({ scenarioId, userInput }) {
  const { token } = useToken();
  const { message } = App.useApp();
  const { state, start, pause, resume, reset } = useScenarioPlayer();

  // 挂载即启动。不加 ref 守卫:React 18 dev StrictMode 双调用
  // (setup → cleanup → setup)中,player 的卸载 cleanup 会 cancel 第一次
  // 启动的 timer;若守卫拦住第二次 setup,回放将永久停在首个事件。
  // start() 幂等:内部先 cancel 旧 timer、再重置状态并推首事件,重复调用安全。
  useEffect(() => {
    start(scenarioId, userInput);
  }, [scenarioId, userInput, start]);

  const scenario = useMemo(() => getScenario(scenarioId), [scenarioId]);

  const exportAuditJson = useCallback(() => {
    if (!scenario) return;
    const payload = {
      scenarioId,
      scenarioTitle: scenario.title,
      userInput,
      status: state.status,
      generatedAt: new Date().toISOString(),
      events: state.events,
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
  }, [scenario, scenarioId, userInput, state.status, state.events, message]);

  const statusTag = useMemo(() => {
    if (state.status === 'running') return { color: 'processing', label: '协作进行中' };
    if (state.status === 'paused') return { color: 'warning', label: '已暂停' };
    if (state.status === 'completed') return { color: 'success', label: '已完成' };
    return { color: 'default', label: '准备中' };
  }, [state.status]);

  return (
    <Card
      size="small"
      className="collab-card"
      styles={{ body: { padding: 12 } }}
      title={
        <Space size={8} wrap>
          <Text strong>{scenario?.title || scenarioId}</Text>
          <Tag bordered={false} color={statusTag.color}>{statusTag.label}</Tag>
          {userInput && (
            <Text type="secondary" style={{ fontSize: 12 }}>· {userInput}</Text>
          )}
        </Space>
      }
      extra={
        <Space size={4}>
          {state.status === 'running' && (
            <Button
              size="small"
              type="text"
              icon={<PauseOutlined />}
              onClick={pause}
            >
              暂停
            </Button>
          )}
          {state.status === 'paused' && (
            <Button
              size="small"
              type="text"
              icon={<PlayCircleOutlined />}
              onClick={resume}
            >
              继续
            </Button>
          )}
          <Button
            size="small"
            type="text"
            icon={<DownloadOutlined />}
            disabled={state.events.length === 0}
            onClick={exportAuditJson}
          >
            审计
          </Button>
          <Button
            size="small"
            type="text"
            danger
            icon={<ReloadOutlined />}
            disabled={state.events.length === 0}
            onClick={reset}
          >
            重置
          </Button>
        </Space>
      }
    >
      <div className="collab-card-body">
        <div className="collab-card-stream">
          <AgentCollabStream
            events={state.events}
            isRunning={state.status === 'running'}
            isCompleted={state.status === 'completed'}
            status={state.status}
          />
        </div>
        <div className="collab-card-timeline">
          <Title level={5} style={{ margin: '4px 0 8px' }}>审计</Title>
          <AuditTimeline events={state.events} activeScenarioId={scenarioId} />
        </div>
      </div>
    </Card>
  );
}
