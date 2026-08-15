/**
 * 规范化聚合查询(aggregated_day)结果。
 * 后端 ResultSynthesizer 返回扁平结构 {summary, items, total_count, moduleCounts, chain_results};
 * 同时兼容未来可能出现的 {data: {...}} 包层结构。
 */
const normalizeAggregatedResult = (result) => {
  if (!result || typeof result !== 'object') return {};
  const wrapped = result.data;
  if (
    wrapped &&
    typeof wrapped === 'object' &&
    (wrapped.items || wrapped.moduleCounts || wrapped.summary)
  ) {
    return wrapped;
  }
  return result;
};

export default normalizeAggregatedResult;
