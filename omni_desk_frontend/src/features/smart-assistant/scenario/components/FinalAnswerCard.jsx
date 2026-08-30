// 最终答案 / 结果展示卡片
// 根据 payloadKind 渲染不同样式
import { Card, Descriptions, List, Space, Tag, Typography, theme } from 'antd';
import {
  CarOutlined,
  FileTextOutlined,
  AlertOutlined,
  AuditOutlined,
  CheckCircleOutlined,
  GlobalOutlined,
  TeamOutlined,
  ClockCircleOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import AgentCard from './AgentCard';

const { Title, Paragraph, Text } = Typography;
const { useToken } = theme;

const PAYLOAD_META = {
  email_draft: { icon: CarOutlined, color: 'blue', title: '出差申请已生成' },
  card_preview: { icon: FileTextOutlined, color: 'purple', title: '可分享摘要' },
  workorder: { icon: AlertOutlined, color: 'red', title: '派单详情' },
  announcement: { icon: AuditOutlined, color: 'gold', title: '合规公告已发布' },
};

/**
 * @param {{
 *   agent: string,
 *   payloadKind?: string,
 *   payload?: Record<string, unknown>,
 * }} props
 */
export default function FinalAnswerCard({ agent, payloadKind, payload, finalOutput, status }) {
  const meta = payloadKind ? PAYLOAD_META[payloadKind] : null;
  const isFailed = status === 'failed';
  const isPartial = status === 'partial';
  const Icon = meta?.icon || (isFailed ? AlertOutlined : CheckCircleOutlined);
  const color = isFailed ? 'red' : isPartial ? 'orange' : meta?.color || 'green';
  const { token } = useToken();

  return (
    <div className="final-answer-card">
      <AgentCard agent={agent} variant="final" content={isFailed ? '任务失败' : isPartial ? '部分完成' : meta?.title || '已完成'} />
      <Card
        className="final-answer-body"
        style={{
          marginTop: 12,
          borderColor: token.colorBorderSecondary,
          borderLeftWidth: 4,
          borderLeftColor: token.colorPrimary,
        }}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center">
            <Icon style={{ fontSize: 22, color: token.colorPrimary }} />
            <Title level={4} style={{ margin: 0 }}>
              {payload?.title || meta?.title || '结果'}
            </Title>
            <Tag color={color} bordered={false}>{payloadKind}</Tag>
          </Space>

          {isFailed && <Text type="danger">任务未完整执行，请检查失败子任务后重试。</Text>}
          {finalOutput !== undefined && !isFailed && (
            <Paragraph data-testid="agent-final-output">
              {typeof finalOutput === 'string' ? finalOutput : '任务结果已生成'}
            </Paragraph>
          )}
          {payloadKind === 'email_draft' && <EmailDraftBody payload={payload} />}
          {payloadKind === 'card_preview' && <CardPreviewBody payload={payload} />}
          {payloadKind === 'workorder' && <WorkorderBody payload={payload} />}
          {payloadKind === 'announcement' && <AnnouncementBody payload={payload} />}
          {!['email_draft', 'card_preview', 'workorder', 'announcement'].includes(payloadKind ?? '') && (
            <Text type="secondary">结果详情已安全隐藏，请查看任务事件获取可展示内容。</Text>
          )}
        </Space>
      </Card>
    </div>
  );
}

function EmailDraftBody({ payload }) {
  return (
    <>
      <Descriptions size="small" column={2} bordered>
        {(payload?.fields || []).map((f) => (
          <Descriptions.Item key={f.label} label={f.label}>
            {f.value}
          </Descriptions.Item>
        ))}
      </Descriptions>
      <div>
        <Text strong>邮件分发：</Text>
        <Tag icon={<TeamOutlined />} bordered={false} color="blue">{payload?.recipients?.email?.join(', ')}</Tag>
      </div>
      <div>
        <Text strong>IM 抄送：</Text>
        <Tag icon={<TeamOutlined />} bordered={false} color="green">{payload?.recipients?.im?.join(', ')}</Tag>
      </div>
    </>
  );
}

function CardPreviewBody({ payload }) {
  return (
    <>
      <Paragraph style={{ marginBottom: 4 }}>
        <Text strong>来源：</Text>
        <Tag bordered={false}>{payload?.source?.id}</Tag>
        <Text>{payload?.source?.title}</Text>
      </Paragraph>
      <Paragraph style={{ marginBottom: 4 }}>{payload?.summary}</Paragraph>
      <Title level={5} style={{ marginTop: 8 }}>关键要点</Title>
      <List
        size="small"
        dataSource={payload?.keyPoints || []}
        renderItem={(item) => (
          <List.Item>
            <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
            {item}
          </List.Item>
        )}
      />
      <Title level={5} style={{ marginTop: 8 }}>行动项</Title>
      <List
        size="small"
        dataSource={payload?.actionItems || []}
        renderItem={(item) => (
          <List.Item>
            <ClockCircleOutlined style={{ color: '#fa8c16', marginRight: 8 }} />
            {item}
          </List.Item>
        )}
      />
      <Paragraph>
        <Text strong>分享链接：</Text>
        <LinkOutlined style={{ marginRight: 6 }} />
        <Text copyable>{payload?.shareUrl}</Text>
      </Paragraph>
    </>
  );
}

function WorkorderBody({ payload }) {
  return (
    <>
      <Descriptions size="small" column={2} bordered>
        {(payload?.fields || []).map((f) => (
          <Descriptions.Item key={f.label} label={f.label}>
            {f.value}
          </Descriptions.Item>
        ))}
      </Descriptions>
      <Title level={5} style={{ marginTop: 8 }}>近期读数</Title>
      <List
        size="small"
        dataSource={payload?.readings || []}
        renderItem={(r) => (
          <List.Item>
            <Text type="secondary" style={{ marginRight: 12, width: 80 }}>{r.ts}</Text>
            <Text strong>{r.value} Pa</Text>
          </List.Item>
        )}
      />
      <Title level={5} style={{ marginTop: 8 }}>维修手册：{payload?.manual?.section}</Title>
      <List
        size="small"
        dataSource={payload?.manual?.steps || []}
        renderItem={(s) => <List.Item>{s}</List.Item>}
      />
    </>
  );
}

function AnnouncementBody({ payload }) {
  return (
    <>
      <Paragraph>{payload?.summary}</Paragraph>
      <Title level={5}>问题清单</Title>
      <List
        size="small"
        dataSource={payload?.findings || []}
        renderItem={(f) => (
          <List.Item>
            <Tag color={f.severity === 'high' ? 'red' : 'orange'} bordered={false}>
              {f.severity.toUpperCase()}
            </Tag>
            <Tag bordered={false}>{f.id}</Tag>
            <Text>{f.rule}</Text>
            <Tag style={{ marginLeft: 8 }} bordered={false}>{f.matched} 起</Tag>
          </List.Item>
        )}
      />
      <Space size="middle">
        <div>
          <Text strong>面向：</Text>
          <Tag icon={<TeamOutlined />} bordered={false}>{payload?.audience}</Tag>
        </div>
        <div>
          <Text strong>截止：</Text>
          <Tag icon={<ClockCircleOutlined />} bordered={false}>{payload?.deadline}</Tag>
        </div>
        <div>
          <Text strong>渠道：</Text>
          {(payload?.channels || []).map((c) => (
            <Tag key={c} icon={<GlobalOutlined />} bordered={false}>{c}</Tag>
          ))}
        </div>
      </Space>
    </>
  );
}
