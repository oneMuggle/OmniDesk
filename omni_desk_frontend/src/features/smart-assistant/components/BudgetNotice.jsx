import { Alert } from 'antd';

/**
 * 今日 AI 额度提示条(方案 5.6)。
 * - readonly:写操作、多步任务和办公文档生成暂停,普通查询不受影响;
 * - blocked:今日 AI 额度已用完,明天 0 点恢复。
 * 正常(null / ok)时不渲染。
 */
const BudgetNotice = ({ budget }) => {
  if (!budget || !budget.state || budget.state === 'ok') return null;
  const blocked = budget.state === 'blocked';
  const fallback = blocked
    ? '今天的 AI 额度已用完，明天 0 点自动恢复；如需调整请联系管理员。'
    : '今天的 AI 额度已接近上限，写操作、多步任务和办公文档生成暂停，普通查询不受影响。';
  return (
    <Alert
      className="smart-chat-budget-notice"
      data-testid="budget-notice"
      type={blocked ? 'error' : 'warning'}
      showIcon
      banner
      message={budget.message || fallback}
    />
  );
};

export default BudgetNotice;
