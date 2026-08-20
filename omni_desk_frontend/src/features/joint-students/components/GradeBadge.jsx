import { Tag } from 'antd';
import PropTypes from 'prop-types';

/**
 * 联培生考核档次徽章。
 * A 档绿色，B 档灰色，未评定 default。
 *
 * @param {{ grade: 'A' | 'B' | string }} props
 * @returns {JSX.Element}
 */
export default function GradeBadge({ grade }) {
  if (grade === 'A') return <Tag color="green">A 档</Tag>;
  if (grade === 'B') return <Tag color="default">B 档</Tag>;
  return <Tag>未评定</Tag>;
}

GradeBadge.propTypes = {
  grade: PropTypes.string,
};
