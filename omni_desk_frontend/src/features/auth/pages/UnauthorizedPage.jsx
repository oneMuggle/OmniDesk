import { useLocation } from 'react-router-dom';
import './UnauthorizedPage.css';

const UnauthorizedPage = () => {
  const location = useLocation();
  const { message, missingPermissions } = location.state || {};

  return (
    <div className="unauthorized-container">
      <h1 className="unauthorized-title">权限不足</h1>
      {message && <p className="unauthorized-message">{message}</p>}
      {missingPermissions && missingPermissions.length > 0 && (
        <div className="unauthorized-permissions">
          <h3>缺少以下权限:</h3>
          <ul>
            {missingPermissions.map((perm, index) => (
              <li key={index}>{perm}</li>
            ))}
          </ul>
        </div>
      )}
      <p>请联系管理员获取相应权限</p>
    </div>
  );
};

export default UnauthorizedPage;
