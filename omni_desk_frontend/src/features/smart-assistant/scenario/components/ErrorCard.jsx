import { Alert, Card, Typography } from 'antd';

const { Text } = Typography;

export default function ErrorCard({ agent = 'system', subtaskId, reason }) {
  const safeReason = typeof reason === 'string' ? reason : '任务执行失败，请稍后重试';
  return (
    <Card size="small" data-testid="agent-error-card">
      <Alert
        type="error"
        showIcon
        message={`${agent}${subtaskId ? `（${subtaskId}）` : ''}执行失败`}
        description={<Text>{safeReason}</Text>}
      />
    </Card>
  );
}
