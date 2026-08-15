import { Fragment } from 'react';
import { Descriptions } from 'antd';
import PropTypes from 'prop-types';
import ResultCardWrapper from './ResultCardWrapper';

/**
 * event_query 事件/日程卡片 — 排班信息 + 节假日两段式。
 * 由注册中心在 result.found 时分发渲染。
 */
const EventQueryCard = ({ result, copyBtn }) => (
  <ResultCardWrapper title="事件/日程" tagColor="magenta" copyBtn={copyBtn}>
    {result.schedules && result.schedules.length > 0 && (
      <Descriptions size="small" column={2} title="排班信息" style={{ marginBottom: 8 }}>
        <Descriptions.Item label="日期">{result.date}</Descriptions.Item>
        {result.schedules.map((s, idx) => (
          <Fragment key={`person-${idx}`}>
            <Descriptions.Item label="值班人员">{s.duty_person}</Descriptions.Item>
            <Descriptions.Item label="值班领导">{s.duty_leader}</Descriptions.Item>
          </Fragment>
        ))}
      </Descriptions>
    )}
    {result.holidays && result.holidays.length > 0 && (
      <Descriptions size="small" column={2} title="节假日">
        {result.holidays.map((h, idx) => (
          <Fragment key={`name-${idx}`}>
            <Descriptions.Item label="名称">{h.name}</Descriptions.Item>
            <Descriptions.Item label="日期">{h.start_date} ~ {h.end_date}</Descriptions.Item>
          </Fragment>
        ))}
      </Descriptions>
    )}
  </ResultCardWrapper>
);

EventQueryCard.propTypes = {
  result: PropTypes.shape({
    found: PropTypes.bool,
    date: PropTypes.string,
    schedules: PropTypes.arrayOf(PropTypes.shape({
      duty_person: PropTypes.string,
      duty_leader: PropTypes.string,
    })),
    holidays: PropTypes.arrayOf(PropTypes.shape({
      name: PropTypes.string,
      start_date: PropTypes.string,
      end_date: PropTypes.string,
    })),
  }).isRequired,
  copyBtn: PropTypes.node,
};

export default EventQueryCard;
