import React from 'react';
import { Skeleton, Table } from 'antd';

const SkeletonTable = ({ columns = 3, rows = 5, loading = true }) => {
  if (!loading) return null;

  const skeletonColumns = Array.from({ length: columns }).map((_, index) => ({
    title: '',
    dataIndex: `col${index}`,
    key: `col${index}`,
    width: 150,
    render: () => <Skeleton active paragraph={false} />,
  }));

  const skeletonData = Array.from({ length: rows }).map((_, rowIndex) => ({
    key: rowIndex,
    ...Object.fromEntries(skeletonColumns.map((col) => [col.dataIndex, null])),
  }));

  return <Table columns={skeletonColumns} dataSource={skeletonData} pagination={false} />;
};

export default SkeletonTable;