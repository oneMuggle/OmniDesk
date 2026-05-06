import { Card, Skeleton } from 'antd';

const CardContainer = ({ title, children, loading = false, extra, ...props }) => {
  if (loading) {
    return (
      <Card title={title} {...props}>
        <Skeleton active paragraph={{ rows: 4 }} />
      </Card>
    );
  }

  return (
    <Card title={title} extra={extra} {...props}>
      {children}
    </Card>
  );
};

export default CardContainer;