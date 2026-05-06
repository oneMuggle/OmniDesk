import { Skeleton } from 'antd';
import PropTypes from 'prop-types';

const SkeletonList = ({ count = 3, active = true }) => {
  if (!active) return null;

  return (
    <>
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} style={{ marginBottom: 16 }}>
          <Skeleton active avatar paragraph={{ rows: 2 }} />
        </div>
      ))}
    </>
  );
};

SkeletonList.propTypes = {
  count: PropTypes.number,
  active: PropTypes.bool,
};

export default SkeletonList;