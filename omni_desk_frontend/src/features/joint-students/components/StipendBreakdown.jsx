import { Descriptions, Statistic } from 'antd';
import PropTypes from 'prop-types';

/**
 * 补助明细展示。
 * 展示基本额度、档次系数、出勤比，最终金额。
 * 当出勤比超过 1 时按 100% 显示（防御后端）。
 *
 * @param {{
 *   record: {
 *     base_amount: string,
 *     grade_coefficient: string,
 *     attendance_ratio: string,
 *     final_amount: string,
 *     student_type: 'master' | 'phd',
 *     grade: 'A' | 'B'
 *   }
 * }} props
 * @returns {JSX.Element}
 */
export default function StipendBreakdown({ record }) {
  const baseAmount = parseFloat(record.base_amount);
  const gradeCoef = parseFloat(record.grade_coefficient);
  const attendanceRatio = parseFloat(record.attendance_ratio);
  const finalAmount = parseFloat(record.final_amount);

  // 防御：出勤比不超过 100%
  const displayRatio = Math.min(attendanceRatio, 1.0);

  return (
    <div>
      <Statistic
        title="最终补助金额"
        value={finalAmount}
        precision={2}
        suffix="元"
        valueStyle={{ color: '#3f8600' }}
      />
      <Descriptions column={1} size="small" style={{ marginTop: 16 }}>
        <Descriptions.Item label="联培生类型">
          {record.student_type === 'master' ? '硕士' : '博士'}
        </Descriptions.Item>
        <Descriptions.Item label="档次">
          {record.grade === 'A' ? 'A 档' : 'B 档'}
        </Descriptions.Item>
        <Descriptions.Item label="基本额度">
          {baseAmount.toFixed(2)} 元
        </Descriptions.Item>
        <Descriptions.Item label="档次系数">
          {gradeCoef.toFixed(2)}
        </Descriptions.Item>
        <Descriptions.Item label="出勤比">
          {(displayRatio * 100).toFixed(0)}%
        </Descriptions.Item>
      </Descriptions>
    </div>
  );
}

StipendBreakdown.propTypes = {
  record: PropTypes.shape({
    base_amount: PropTypes.string.isRequired,
    grade_coefficient: PropTypes.string.isRequired,
    attendance_ratio: PropTypes.string.isRequired,
    final_amount: PropTypes.string.isRequired,
    student_type: PropTypes.string.isRequired,
    grade: PropTypes.string.isRequired,
  }).isRequired,
};
