import { Empty, Space, Spin, Tag, Timeline, Typography } from 'antd';
import PropTypes from 'prop-types';
import { EVENT_TYPE_LABELS } from '../../api/agentTaskApi';
import { eventColor, formatPayload, formatTime } from '../../utils/agentTaskUtils';

const AgentLogStream = ({ events, detailLoading }) => (
  <div>
    <Space size={8}>
      <Typography.Text strong>执行时间线</Typography.Text>
      {detailLoading && <Spin size="small" />}
    </Space>
    {events.length === 0 ? (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description="暂无事件"
        style={{ marginTop: 12 }}
      />
    ) : (
      <Timeline
        style={{ marginTop: 12 }}
        items={events.map((event) => {
          const payloadText = formatPayload(event.payload);
          return {
            color: eventColor(event.type),
            children: (
              <div key={event.key}>
                <Space size={8} wrap>
                  <span>{EVENT_TYPE_LABELS[event.type] || event.type}</span>
                  {event.subtaskRef && <Tag>{event.subtaskRef}</Tag>}
                  {event.time && (
                    <Typography.Text type="secondary">
                      {formatTime(event.time)}
                    </Typography.Text>
                  )}
                </Space>
                {payloadText && (
                  <div>
                    <Typography.Text type="secondary">{payloadText}</Typography.Text>
                  </div>
                )}
              </div>
            ),
          };
        })}
      />
    )}
  </div>
);

AgentLogStream.propTypes = {
  events: PropTypes.array,
  detailLoading: PropTypes.bool,
};

export default AgentLogStream;
