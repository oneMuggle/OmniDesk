import { Descriptions, Badge } from 'antd';
import PropTypes from 'prop-types';
import ResultCardWrapper from './ResultCardWrapper';

/**
 * memo_query 备忘录卡片。
 * 由注册中心在 result.found && result.memos 时分发渲染。
 */
const MemoQueryCard = ({ result, copyBtn }) => (
  <ResultCardWrapper title="备忘录" tagColor="cyan" copyBtn={copyBtn}>
    {result.memos.map((m, idx) => (
      <Descriptions key={idx} size="small" column={2} style={{ marginBottom: idx < result.memos.length - 1 ? 8 : 0 }}>
        <Descriptions.Item label="标题">{m.title}</Descriptions.Item>
        <Descriptions.Item label="完成状态">
          <Badge status={m.is_completed ? 'success' : 'default'} text={m.is_completed ? '已完成' : '未完成'} />
        </Descriptions.Item>
        <Descriptions.Item label="内容" span={2}>{m.content}</Descriptions.Item>
        <Descriptions.Item label="创建人">{m.user}</Descriptions.Item>
        <Descriptions.Item label="创建日期">{m.created_at}</Descriptions.Item>
        {m.reminder_time !== '无提醒' && <Descriptions.Item label="提醒时间">{m.reminder_time}</Descriptions.Item>}
      </Descriptions>
    ))}
  </ResultCardWrapper>
);

MemoQueryCard.propTypes = {
  result: PropTypes.shape({
    found: PropTypes.bool,
    memos: PropTypes.arrayOf(PropTypes.shape({
      title: PropTypes.string,
      content: PropTypes.string,
      user: PropTypes.string,
      is_completed: PropTypes.bool,
      reminder_time: PropTypes.string,
      created_at: PropTypes.string,
    })),
  }).isRequired,
  copyBtn: PropTypes.node,
};

export default MemoQueryCard;
