import PropTypes from 'prop-types';
import { Navigate, generatePath, useLocation, useParams } from 'react-router-dom';

/**
 * 旧地址重定向(S2-2 AI 入口收敛)。
 * - ``to`` 可含路由参数(如 ``/smart-assistant/apps/dify/:appId``),用当前地址的参数填充;
 * - 保留查询参数和 hash,旧书签 / 外部链接带的 ``?session=`` 等不会丢;
 * - 使用 replace,浏览器"后退"不会再回到旧地址。
 */
const LegacyRedirect = ({ to }) => {
  const params = useParams();
  const { search, hash } = useLocation();
  return <Navigate to={`${generatePath(to, params)}${search}${hash}`} replace />;
};

LegacyRedirect.propTypes = {
  to: PropTypes.string.isRequired,
};

export default LegacyRedirect;
