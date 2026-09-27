import PropTypes from 'prop-types';
import { Button, Card, Space, Tag, Typography } from 'antd';
import { ApartmentOutlined } from '@ant-design/icons';

/** 各状态下的提示文案;idle 时不显示 */
const STATUS_TEXT = {
  creating: '正在创建协作任务…',
  created: '已创建协作任务,进度见下方卡片',
  answered: '已改为直接回答',
  error: '任务创建失败,请稍后重试',
};

/**
 * 任务计划卡(S2):意图为 complex_task 时展示任务目标,由用户决定
 * 创建多 Agent 协作任务,或改为直接回答。按钮点击一次后即锁定,
 * 避免重复创建任务。
 */
const TaskProposalCard = ({ proposal, status = 'idle', onCreate, onAnswerDirectly }) => {
  if (!proposal || !proposal.objective) return null;
  const locked = status !== 'idle' && status !== 'error';
  return (
    <Card
      size="small"
      className="task-proposal-card"
      data-testid="task-proposal-card"
      title={(
        <Space size={6}>
          <ApartmentOutlined />
          <span>任务计划</span>
          <Tag color="blue">多 Agent 协作</Tag>
        </Space>
      )}
      style={{ marginTop: 8, maxWidth: 520 }}
    >
      <Typography.Paragraph style={{ marginBottom: 8 }}>
        <Typography.Text type="secondary">任务目标:</Typography.Text>
        {proposal.objective}
      </Typography.Paragraph>
      <Space wrap>
        <Button
          type="primary"
          size="small"
          loading={status === 'creating'}
          disabled={locked}
          onClick={onCreate}
        >
          创建协作任务
        </Button>
        <Button size="small" disabled={locked} onClick={onAnswerDirectly}>
          直接回答
        </Button>
      </Space>
      {STATUS_TEXT[status] && (
        <Typography.Text
          type={status === 'error' ? 'danger' : 'secondary'}
          style={{ display: 'block', marginTop: 8 }}
          data-testid="task-proposal-status"
        >
          {STATUS_TEXT[status]}
        </Typography.Text>
      )}
    </Card>
  );
};

TaskProposalCard.propTypes = {
  proposal: PropTypes.shape({
    objective: PropTypes.string,
    mode: PropTypes.string,
  }),
  status: PropTypes.oneOf(['idle', 'creating', 'created', 'answered', 'error']),
  onCreate: PropTypes.func.isRequired,
  onAnswerDirectly: PropTypes.func.isRequired,
};

export default TaskProposalCard;

