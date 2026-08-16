import { useEffect, useMemo } from 'react';
import { Modal, Form, Input, DatePicker, Select, Button } from 'antd';
import PropTypes from 'prop-types';

const { Option } = Select;

/**
 * 排班新增/编辑表单 Modal。
 * R4-B4: 从 ScheduleManagementPage.jsx 外拆,保持原 testid/行为不变。
 */
const ScheduleFormModal = ({ open, onCancel, onOk, initialValues, personnelList, positions }) => {
  const [form] = Form.useForm();
  const selectedPersonPositionId = Form.useWatch('person_position_filter', form);
  const selectedLeaderPositionId = Form.useWatch('leader_position_filter', form);

  // Use initialValues as fallback when Form.useWatch hasn't picked up the value yet
  const effectivePersonPositionId = selectedPersonPositionId ?? initialValues?.person_position_filter;
  const effectiveLeaderPositionId = selectedLeaderPositionId ?? initialValues?.leader_position_filter;

  // Get currently selected person/leader IDs to ensure they're always in the options
  const selectedPersonId = Form.useWatch('duty_person', form);
  const selectedLeaderId = Form.useWatch('duty_leader', form);

  const filteredDutyPersonList = useMemo(() => {
    if (!effectivePersonPositionId) return personnelList;
    const filteredPersonnel = personnelList.filter(p => {
      // Always include the currently selected person
      if (selectedPersonId != null && Number(p.id) === Number(selectedPersonId)) return true;
      return Number(p.position?.id) === Number(effectivePersonPositionId);
    });
    return filteredPersonnel;
  }, [personnelList, effectivePersonPositionId, selectedPersonId]);

  const filteredDutyLeaderList = useMemo(() => {
    if (!effectiveLeaderPositionId) return personnelList;
    const filteredLeaders = personnelList.filter(p => {
      // Always include the currently selected leader
      if (selectedLeaderId != null && Number(p.id) === Number(selectedLeaderId)) return true;
      return Number(p.position?.id) === Number(effectiveLeaderPositionId);
    });
    return filteredLeaders;
  }, [personnelList, effectiveLeaderPositionId, selectedLeaderId]);

  // Sync form values when modal opens with new initialValues
  useEffect(() => {
    if (open) {
      // Set form values explicitly
      form.setFieldsValue(initialValues || {});
    } else {
      form.resetFields();
    }
  }, [open]);

  const handleOk = () => {
    form.validateFields()
      .then(values => {
        const submitData = {
          date: values.date ? values.date.format('YYYY-MM-DD') : null,
          duty_person_id: values.duty_person, // 映射到后端期望的字段名
          duty_leader_id: values.duty_leader, // 映射到后端期望的字段名
          // 移除 person_position_filter 和 leader_position_filter，它们只用于前端筛选
        };
        onOk(submitData);
        form.resetFields();
      })
      .catch(() => {
      });
  };

  return (
    <Modal
      title={initialValues.id ? "编辑排班" : "新增排班"}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnHidden
      data-testid="schedule-modal"
      footer={[
        <Button key="back" onClick={onCancel}>
          取消
        </Button>,
        <Button key="submit" type="primary" onClick={handleOk} data-testid="schedule-modal-ok-button">
          确定
        </Button>,
      ]}
    >
      <Form
        form={form}
        layout="vertical"
        key={initialValues.id || 'new'}
        initialValues={initialValues}
      >
        <Form.Item
          name="date"
          label="值班日期"
          rules={[{ required: true, message: '请选择值班日期!' }]}
        >
          <DatePicker style={{ width: '100%' }} data-testid="schedule-modal-date-picker" />
        </Form.Item>
        <Form.Item
          name="person_position_filter"
          label="值班人员职务筛选"
        >
          <Select
            placeholder="按职务筛选值班人员"
            allowClear
          >
            {positions.map(position => (
              <Option key={position.id} value={position.id}>
                {position.name}
              </Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item
          name="duty_person"
          label="值班人员"
          rules={[{ required: true, message: '请选择值班人员!' }]}
        >
          <Select
            placeholder="选择值班人员"
            showSearch
            data-testid="schedule-modal-duty-person-select"
            classNames={{ popup: { root: 'duty-person-select-dropdown' } }}
            filterOption={(input, option) =>
              (option?.children ?? []).join('').toLowerCase().includes(input.toLowerCase())
            }
          >
            {filteredDutyPersonList.map(user => (
              <Select.Option key={user.id} value={user.id} data-testid={`duty-person-option-${user.id}`}>
                {user.position?.name ? `${user.name} (${user.position.name})` : user.name}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
        {initialValues?.duty_person_phone && (
          <Form.Item label="值班人员电话">
            <Input value={initialValues.duty_person_phone} readOnly data-testid="schedule-modal-duty-person-phone" />
          </Form.Item>
        )}
        <Form.Item
          name="leader_position_filter"
          label="值班领导职务筛选"
        >
          <Select
            placeholder="按职务筛选值班领导"
            allowClear
          >
            {positions.map(position => (
              <Option key={position.id} value={position.id}>
                {position.name}
              </Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item
          name="duty_leader"
          label="值班领导"
          rules={[{ required: true, message: '请选择值班领导!' }]}
        >
          <Select
            placeholder="选择值班领导"
            showSearch
            data-testid="schedule-modal-duty-leader-select"
            classNames={{ popup: { root: 'duty-leader-select-dropdown' } }}
            filterOption={(input, option) =>
              (option?.children ?? []).join('').toLowerCase().includes(input.toLowerCase())
            }
          >
            {filteredDutyLeaderList.map(user => (
              <Select.Option key={user.id} value={user.id} data-testid={`duty-leader-option-${user.id}`}>
                {user.position?.name ? `${user.name} (${user.position.name})` : user.name}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
        {initialValues?.duty_leader_phone && (
          <Form.Item label="值班领导电话">
            <Input value={initialValues.duty_leader_phone} readOnly data-testid="schedule-modal-duty-leader-phone" />
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
};

ScheduleFormModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onCancel: PropTypes.func.isRequired,
  onOk: PropTypes.func.isRequired,
  initialValues: PropTypes.object,
  personnelList: PropTypes.array.isRequired,
  positions: PropTypes.array.isRequired,
};

ScheduleFormModal.defaultProps = {
  initialValues: {},
};

export default ScheduleFormModal;
