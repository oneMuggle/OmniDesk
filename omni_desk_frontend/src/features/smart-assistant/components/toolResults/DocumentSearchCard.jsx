import { Descriptions } from 'antd';
import PropTypes from 'prop-types';
import ResultCardWrapper from './ResultCardWrapper';

/**
 * document_search 文档搜索卡片。
 * 由注册中心在 result.found && result.documents 时分发渲染。
 */
const DocumentSearchCard = ({ result, copyBtn }) => (
  <ResultCardWrapper title="文档搜索" tagColor="orange" copyBtn={copyBtn}>
    {result.documents.map((doc, idx) => (
      <Descriptions key={idx} size="small" column={2} style={{ marginBottom: idx < result.documents.length - 1 ? 8 : 0 }}>
        <Descriptions.Item label="类型">{doc.type}</Descriptions.Item>
        <Descriptions.Item label="标题">{doc.title}</Descriptions.Item>
        {doc.experiment_type && <Descriptions.Item label="实验类型">{doc.experiment_type}</Descriptions.Item>}
        {doc.client && <Descriptions.Item label="客户">{doc.client}</Descriptions.Item>}
        {doc.status && <Descriptions.Item label="状态">{doc.status}</Descriptions.Item>}
        {doc.owner && <Descriptions.Item label="创建人">{doc.owner}</Descriptions.Item>}
        {doc.start_date && <Descriptions.Item label="开始日期">{doc.start_date}</Descriptions.Item>}
        {doc.created_at && <Descriptions.Item label="创建时间">{doc.created_at}</Descriptions.Item>}
      </Descriptions>
    ))}
  </ResultCardWrapper>
);

DocumentSearchCard.propTypes = {
  result: PropTypes.shape({
    found: PropTypes.bool,
    documents: PropTypes.arrayOf(PropTypes.shape({
      type: PropTypes.string,
      title: PropTypes.string,
      experiment_type: PropTypes.string,
      owner: PropTypes.string,
      client: PropTypes.string,
      status: PropTypes.string,
      start_date: PropTypes.string,
      created_at: PropTypes.string,
    })),
  }).isRequired,
  copyBtn: PropTypes.node,
};

export default DocumentSearchCard;
