import { Tag } from 'antd';
import PropTypes from 'prop-types';
import ResultCardWrapper from './ResultCardWrapper';

/**
 * knowledge_qa 引用来源卡片 — 使用 sources prop(非 result)。
 * 由注册中心在 sources 非空时分发渲染。
 */
const KnowledgeQaCard = ({ sources, copyBtn }) => (
  <ResultCardWrapper title="引用来源" tagColor="purple" copyBtn={copyBtn}>
    <ul className="sources-list">
      {sources.map((source, idx) => (
        <li key={idx}>
          {source.document}
          {source.score > 0 && <Tag style={{ marginLeft: 8 }}>相似度: {(source.score * 100).toFixed(0)}%</Tag>}
        </li>
      ))}
    </ul>
  </ResultCardWrapper>
);

KnowledgeQaCard.propTypes = {
  sources: PropTypes.arrayOf(PropTypes.shape({
    document: PropTypes.string,
    score: PropTypes.number,
  })).isRequired,
  copyBtn: PropTypes.node,
};

export default KnowledgeQaCard;
