import { Card, Skeleton } from 'antd';

const SkeletonCard = ({ title, rows = 3 }) => {
  return (
    <Card title={title}>
      <Skeleton active paragraph={{ rows }} />
    </Card>
  );
};

export default SkeletonCard;