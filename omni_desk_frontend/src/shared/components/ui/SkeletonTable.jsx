import { Skeleton, Table } from 'antd';

const SkeletonTable = ({ rows = 5, columns = 3 }) => {
  const skeletonColumns = Array.from({ length: columns }, (_, i) => ({
    key: `col-${i}`,
    title: <Skeleton.Input active style={{ width: 80 }} />,
    dataIndex: `col-${i}`,
    render: () => <Skeleton.Input active style={{ width: '100%' }} />
  }));

  const skeletonData = Array.from({ length: rows }, (_, i) => ({
    key: `row-${i}`,
    ...Object.fromEntries(skeletonColumns.map(col => [col.dataIndex, null]))
  }));

  return <Table columns={skeletonColumns} dataSource={skeletonData} pagination={false} />;
};

export default SkeletonTable;