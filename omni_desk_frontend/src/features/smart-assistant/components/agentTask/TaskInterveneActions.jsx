import { Button, Popconfirm, Space } from 'antd';
import { PauseCircleOutlined, PlayCircleOutlined, StopOutlined } from '@ant-design/icons';

const TaskInterveneActions = ({ status, interveneLoading, onIntervene }) => {
  const canPause = status === 'running';
  const canResume = status === 'paused';
  const canCancel = canPause || canResume;

  return (
    <Space wrap>
      <Button
        size="small"
        icon={<PauseCircleOutlined />}
        disabled={!canPause}
        loading={interveneLoading}
        onClick={() => onIntervene('pause')}
      >
        暂停
      </Button>
      <Button
        size="small"
        icon={<PlayCircleOutlined />}
        disabled={!canResume}
        loading={interveneLoading}
        onClick={() => onIntervene('resume')}
      >
        恢复
      </Button>
      <Popconfirm
        title="确认终止该任务？"
        description="终止后任务不可恢复。"
        okText="终止"
        cancelText="取消"
        okButtonProps={{ danger: true }}
        onConfirm={() => onIntervene('cancel')}
      >
        <Button
          size="small"
          danger
          icon={<StopOutlined />}
          disabled={!canCancel}
          loading={interveneLoading}
        >
          终止
        </Button>
      </Popconfirm>
    </Space>
  );
};

export default TaskInterveneActions;
