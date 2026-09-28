import { useEffect } from 'react';
import PropTypes from 'prop-types';
import { useSearchParams } from 'react-router-dom';
import { message as antMessage } from 'antd';
import { getProposal } from '../api/smartAssistantApi';

/**
 * 数字员工通知链接 /smart-assistant?proposal=<id> 的处理（S4-1）。
 *
 * 读到参数后拉取待确认事项并交给 ``onProposal`` 插入确认卡，然后去掉地址里的参数，
 * 避免刷新页面重复插入。已在智能助手页时再点另一条通知也会触发（依赖地址参数变化）。
 * 不渲染任何内容；只应在 Router 内使用。
 */
const ProposalLinkWatcher = ({ onProposal }) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const proposalId = searchParams.get('proposal');

  useEffect(() => {
    if (!proposalId) return undefined;
    let cancelled = false;
    getProposal(proposalId)
      .then(({ data }) => {
        if (!cancelled) onProposal(data);
      })
      .catch(() => {
        if (!cancelled) antMessage.error('待确认事项不存在或无权查看');
      })
      .finally(() => {
        if (!cancelled) {
          setSearchParams((prev) => {
            const next = new URLSearchParams(prev);
            next.delete('proposal');
            return next;
          }, { replace: true });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [proposalId, onProposal, setSearchParams]);

  return null;
};

ProposalLinkWatcher.propTypes = {
  onProposal: PropTypes.func.isRequired,
};

export default ProposalLinkWatcher;
