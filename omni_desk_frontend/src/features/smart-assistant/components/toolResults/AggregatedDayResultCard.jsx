import PropTypes from 'prop-types';
import AggregatedDayCard from '../AggregatedDayCard';
import normalizeAggregatedResult from '../../utils/normalizeAggregatedResult';

/**
 * aggregated_day 结果卡片 — 规范化扁平/包层结构后复用 AggregatedDayCard。
 * 空态({summary: '未找到相关信息', ...})由 AggregatedDayCard 内部 Empty 兜底。
 */
const AggregatedDayResultCard = ({ result, copyBtn }) => {
  const aggData = normalizeAggregatedResult(result);
  return (
    <div className="tool-result-card">
      <AggregatedDayCard
        items={aggData.items}
        moduleCounts={aggData.moduleCounts}
        summary={aggData.summary}
      />
      {copyBtn}
    </div>
  );
};

AggregatedDayResultCard.propTypes = {
  result: PropTypes.object,
  copyBtn: PropTypes.node,
};

export default AggregatedDayResultCard;
