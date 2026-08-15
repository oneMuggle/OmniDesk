import { Alert, Button, Card, Input, Space } from 'antd';
import { SendOutlined } from '@ant-design/icons';

const TaskCreateForm = ({ goal, createLoading, createError, onGoalChange, onCreate }) => (
  <Card size="small" style={{ marginBottom: 16 }}>
    <Space.Compact style={{ width: '100%' }}>
      <Input
        placeholder="描述任务目标，如：调研 RAG 技术并整理成报告"
        value={goal}
        onChange={(e) => onGoalChange(e.target.value)}
        onPressEnter={onCreate}
        disabled={createLoading}
        allowClear
      />
      <Button type="primary" icon={<SendOutlined />} loading={createLoading} onClick={onCreate}>
        创建并执行
      </Button>
    </Space.Compact>
    {createError && (
      <Alert type="error" showIcon message={createError} style={{ marginTop: 8 }} />
    )}
  </Card>
);

export default TaskCreateForm;
