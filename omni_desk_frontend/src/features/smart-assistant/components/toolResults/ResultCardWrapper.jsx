import { Card, Tag } from 'antd';
import PropTypes from 'prop-types';

/**
 * 通用结果卡片包装器 — 消除重复的 wrapper 结构。
 * 所有 intent 分支共享: div.tool-result-card > Card + 复制按钮
 */
const ResultCardWrapper = ({ title, tagColor, children, copyBtn }) => (
  <div className="tool-result-card">
    <Card size="small" title={<Tag color={tagColor}>{title}</Tag>}>
      {children}
    </Card>
    {copyBtn}
  </div>
);

ResultCardWrapper.propTypes = {
  title: PropTypes.string.isRequired,
  tagColor: PropTypes.string.isRequired,
  children: PropTypes.node.isRequired,
  copyBtn: PropTypes.node.isRequired,
};

export default ResultCardWrapper;
