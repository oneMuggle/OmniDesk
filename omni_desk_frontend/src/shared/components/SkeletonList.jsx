import React from 'react';
import { Skeleton } from 'antd';

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

export default SkeletonList;