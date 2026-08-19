import { Descriptions, Badge } from 'antd';
import PropTypes from 'prop-types';
import ResultCardWrapper from './ResultCardWrapper';

/**
 * personnel_query 人员信息卡片。
 * 由注册中心在 result.found 时分发渲染。
 */
const PersonnelResultCard = ({ result, copyBtn }) => (
  <ResultCardWrapper title="人员信息" tagColor="green" copyBtn={copyBtn}>
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
  </ResultCardWrapper>
);

PersonnelResultCard.propTypes = {
  result: PropTypes.shape({
    found: PropTypes.bool,
    personnel: PropTypes.arrayOf(PropTypes.shape({
      name: PropTypes.string,
      department: PropTypes.string,
      position: PropTypes.string,
      status: PropTypes.string,
      phone_number: PropTypes.string,
    })),
  }).isRequired,
  copyBtn: PropTypes.node,
};

export default PersonnelResultCard;
