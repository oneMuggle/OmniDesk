import React from 'react';
import { TimePicker } from 'antd';

const CustomTimeRangePicker = ({ value, onChange, disabled }) => {
  return (
    <TimePicker.RangePicker
      format="HH:mm"
      value={value}
      onChange={onChange}
      disabled={disabled}
      getPopupContainer={() => document.body} // 强制渲染到 body
      style={{ width: '100%' }} // 确保宽度适应父容器
    />
  );
};

export default CustomTimeRangePicker;