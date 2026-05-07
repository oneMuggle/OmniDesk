import { Card, Descriptions, Tag, Badge } from 'antd';
import PropTypes from 'prop-types';
import './ToolResult.css';

const ToolResult = ({ intent, result, sources }) => {
  if (!result) return null;

  if (intent === 'schedule_query' && result.found) {
    return (
      <div className="tool-result-card">
        <Card size="small" title={<Tag color="blue">排班信息</Tag>}>
          {result.schedules.map((schedule, idx) => (
            <Descriptions key={idx} size="small" column={2} style={{ marginBottom: idx < result.schedules.length - 1 ? 8 : 0 }}>
              <Descriptions.Item label="日期">{schedule.duty_date}</Descriptions.Item>
              <Descriptions.Item label="值班人员">{schedule.duty_person}</Descriptions.Item>
              <Descriptions.Item label="值班领导">{schedule.duty_leader}</Descriptions.Item>
            </Descriptions>
          ))}
        </Card>
      </div>
    );
  }

  if (intent === 'personnel_query' && result.found) {
    return (
      <div className="tool-result-card">
        <Card size="small" title={<Tag color="green">人员信息</Tag>}>
          {result.personnel.map((p, idx) => (
            <Descriptions key={idx} size="small" column={2} style={{ marginBottom: idx < result.personnel.length - 1 ? 8 : 0 }}>
              <Descriptions.Item label="姓名">{p.name}</Descriptions.Item>
              <Descriptions.Item label="部门">{p.department}</Descriptions.Item>
              <Descriptions.Item label="职位">{p.position}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Badge status={p.status === '在职' ? 'success' : 'default'} text={p.status} />
              </Descriptions.Item>
              <Descriptions.Item label="电话">{p.phone_number}</Descriptions.Item>
            </Descriptions>
          ))}
        </Card>
      </div>
    );
  }

  if (intent === 'knowledge_qa' && sources && sources.length > 0) {
    return (
      <div className="tool-result-card">
        <Card size="small" title={<Tag color="purple">引用来源</Tag>}>
          <ul className="sources-list">
            {sources.map((source, idx) => (
              <li key={idx}>
                {source.document}
                {source.score > 0 && <Tag style={{ marginLeft: 8 }}>相似度: {(source.score * 100).toFixed(0)}%</Tag>}
              </li>
            ))}
          </ul>
        </Card>
      </div>
    );
  }

  if (!result.found) {
    return (
      <div className="tool-result-card">
        <Tag color="default">{result.message || '未找到相关信息'}</Tag>
      </div>
    );
  }

  return null;
};

export default ToolResult;

ToolResult.propTypes = {
  intent: PropTypes.string,
  result: PropTypes.shape({
    found: PropTypes.bool,
    schedules: PropTypes.arrayOf(PropTypes.shape({
      duty_date: PropTypes.string,
      duty_person: PropTypes.string,
      duty_leader: PropTypes.string,
    })),
    personnel: PropTypes.arrayOf(PropTypes.shape({
      name: PropTypes.string,
      department: PropTypes.string,
      position: PropTypes.string,
      status: PropTypes.string,
      phone_number: PropTypes.string,
    })),
    message: PropTypes.string,
  }),
  sources: PropTypes.arrayOf(PropTypes.shape({
    document: PropTypes.string,
    score: PropTypes.number,
  })),
};
