import { useState } from 'react';
import { Modal, Form, Input, DatePicker, Select, Radio } from 'antd';
import PropTypes from 'prop-types';

const { Option } = Select;

/**
 * 生成排班 Modal。
 * R4-B4: 从 ScheduleManagementPage.jsx 外拆,保持原 testid/行为不变。
 */
const GenerateScheduleModal = ({ open, onCancel, onOk, personnelSequences, leaderSequences }) => {
  const [form] = Form.useForm();
  const [generationMode, setGenerationMode] = useState('days');
  const [selectedPersonnel, setSelectedPersonnel] = useState([]);
  const [selectedHolidayPersonnel, setSelectedHolidayPersonnel] = useState([]);
  const [selectedLeaders, setSelectedLeaders] = useState([]);

  const handleOk = () => {
    form.validateFields()
      .then(values => {
        const submitData = { ...values };
        if (values.start_date) {
          submitData.start_date = values.start_date.format('YYYY-MM-DD');
        }
        if (values.target_month) {
          submitData.target_month = values.target_month.format('YYYY-MM');
        }
        onOk(submitData);
        form.resetFields();
        setSelectedPersonnel([]);
        setSelectedHolidayPersonnel([]);
        setSelectedLeaders([]);
      })
      .catch(() => {
      });
  };

  const handleSequenceChange = (type, sequenceId) => {
    if (type === 'workday') {
      const sequence = personnelSequences.find(s => s.id === sequenceId);
      const personnelDetails = sequence?.personnel_details;
      setSelectedPersonnel(personnelDetails || []);
      form.setFieldsValue({ start_personnel_id: null });
    } else if (type === 'holiday') {
      const sequence = personnelSequences.find(s => s.id === sequenceId);
      setSelectedHolidayPersonnel(sequence?.personnel_details || []);
      form.setFieldsValue({ start_holiday_personnel_id: null });
    } else if (type === 'leader') {
      const sequence = leaderSequences.find(s => s.id === sequenceId);
      setSelectedLeaders(sequence?.personnel_details || []);
      form.setFieldsValue({ start_leader_id: null });
    }
  };

  return (
    <Modal title="生成排班" open={open} onOk={handleOk} onCancel={onCancel} destroyOnHidden data-testid="generate-schedule-modal">
      <Form form={form} layout="vertical" initialValues={{ generationMode: 'days' }}>
        <Form.Item name="generationMode" label="生成方式">
          <Radio.Group onChange={(e) => setGenerationMode(e.target.value)}>
            <Radio value="days">按天数</Radio>
            <Radio value="month">按月份</Radio>
          </Radio.Group>
        </Form.Item>

        {generationMode === 'days' ? (
          <>
            <Form.Item name="start_date" label="起始日期" rules={[{ required: true, message: '请选择起始日期!' }]}>
              <DatePicker style={{ width: '100%' }} data-testid="generate-schedule-start-date" />
            </Form.Item>
            <Form.Item name="duration_days" label="生成天数" initialValue={30} rules={[{ required: true, message: '请输入生成天数!' }]}>
              <Input type="number" data-testid="generate-schedule-duration-days" />
            </Form.Item>
          </>
        ) : (
          <Form.Item name="target_month" label="选择月份" rules={[{ required: true, message: '请选择月份!' }]}>
            <DatePicker picker="month" style={{ width: '100%' }} data-testid="generate-schedule-target-month" />
          </Form.Item>
        )}

        <Form.Item name="workday_personnel_sequence_id" label="人员顺序 (工作日)" rules={[{ required: true, message: '请选择工作日人员顺序!' }]}>
          <Select placeholder="选择工作日人员顺序" onChange={(value) => handleSequenceChange('workday', value)} data-testid="generate-schedule-workday-personnel-sequence" classNames={{ popup: { root: 'workday-sequence-select-dropdown' } }}>
            {Array.isArray(personnelSequences) && personnelSequences.map(seq => (
              <Option key={seq.id} value={seq.id} data-testid={`workday-sequence-option-${seq.id}`}>
                {seq.name} (工作日: {Array.isArray(seq.personnel_details) ? seq.personnel_details.map(p => p.name).join(', ') : ''})
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item name="start_personnel_id" label="起始人员 (工作日)">
          <Select placeholder="选择工作日起始人员" allowClear data-testid="generate-schedule-start-personnel" classNames={{ popup: { root: 'start-personnel-select-dropdown' } }}>
            {
              (() => {
                if (!Array.isArray(selectedPersonnel)) {
                  return null;
                }
                const filteredPersonnel = selectedPersonnel.filter(p => p && p.id != null);

                const weekdayPersonnelOptions = filteredPersonnel.map(p => (
                  <Option key={p.id} value={p.id} data-testid={`start-personnel-option-${p.id}`}>{p.name}</Option>
                ));

                return weekdayPersonnelOptions;
              })()
            }
          </Select>
        </Form.Item>

        <Form.Item name="holiday_personnel_sequence_id" label="人员顺序 (节假日)" rules={[{ required: true, message: '请选择节假日人员顺序!' }]}>
          <Select placeholder="选择节假日人员顺序" onChange={(value) => handleSequenceChange('holiday', value)} data-testid="generate-schedule-holiday-personnel-sequence" classNames={{ popup: { root: 'holiday-sequence-select-dropdown' } }}>
            {Array.isArray(personnelSequences) && personnelSequences.map(seq => (
              <Option key={seq.id} value={seq.id} data-testid={`holiday-sequence-option-${seq.id}`}>
                {seq.name} (节假日: {Array.isArray(seq.personnel_details) ? seq.personnel_details.map(p => p.name).join(', ') : ''})
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item name="start_holiday_personnel_id" label="起始人员 (节假日)">
          <Select placeholder="选择节假日起始人员" allowClear data-testid="generate-schedule-start-holiday-personnel" classNames={{ popup: { root: 'start-holiday-personnel-select-dropdown' } }}>
            {selectedHolidayPersonnel.filter(p => p && p.id != null).map(p => (
              <Option key={p.id} value={p.id} data-testid={`start-holiday-personnel-option-${p.id}`}>{p.name}</Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item name="leader_sequence_id" label="领导顺序" rules={[{ required: true, message: '请选择领导顺序!' }]}>
          <Select placeholder="选择领导顺序" onChange={(value) => handleSequenceChange('leader', value)} data-testid="generate-schedule-leader-sequence" classNames={{ popup: { root: 'leader-sequence-select-dropdown' } }}>
            {Array.isArray(leaderSequences) && leaderSequences.map(seq => (
              <Option key={seq.id} value={seq.id} data-testid={`leader-sequence-option-${seq.id}`}>
                {seq.name} ({Array.isArray(seq.personnel_details) ? seq.personnel_details.map(p => p.name).join(', ') : ''})
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item name="start_leader_id" label="起始领导">
          <Select placeholder="选择起始领导" allowClear data-testid="generate-schedule-start-leader" classNames={{ popup: { root: 'start-leader-select-dropdown' } }}>
            {selectedLeaders.map(p => (
              <Option key={p.id} value={p.id}>{p.name}</Option>
            ))}
          </Select>
        </Form.Item>
      </Form>
    </Modal>
  );
};

GenerateScheduleModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onCancel: PropTypes.func.isRequired,
  onOk: PropTypes.func.isRequired,
  personnelSequences: PropTypes.array.isRequired,
  leaderSequences: PropTypes.array.isRequired,
};

export default GenerateScheduleModal;
