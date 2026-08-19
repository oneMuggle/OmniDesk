import { Descriptions } from 'antd';
import PropTypes from 'prop-types';
import ResultCardWrapper from './ResultCardWrapper';

/**
 * schedule_query 排班信息卡片。
 * 由注册中心在 result.found 时分发渲染。
 */
const ScheduleResultCard = ({ result, copyBtn }) => (
  <ResultCardWrapper title="排班信息" tagColor="blue" copyBtn={copyBtn}>
    {result.schedules.map((schedule, idx) => (
      <Descriptions key={idx} size="small" column={2} style={{ marginBottom: idx < result.schedules.length - 1 ? 8 : 0 }}>
        <Descriptions.Item label="日期">{schedule.duty_date}</Descriptions.Item>
        <Descriptions.Item label="值班人员">{schedule.duty_person}</Descriptions.Item>
        <Descriptions.Item label="值班领导">{schedule.duty_leader}</Descriptions.Item>
      </Descriptions>
    ))}
  </ResultCardWrapper>
);

ScheduleResultCard.propTypes = {
  result: PropTypes.shape({
    found: PropTypes.bool,
    schedules: PropTypes.arrayOf(PropTypes.shape({
      duty_date: PropTypes.string,
      duty_person: PropTypes.string,
      duty_leader: PropTypes.string,
    })),
  }).isRequired,
  copyBtn: PropTypes.node,
};

export default ScheduleResultCard;
