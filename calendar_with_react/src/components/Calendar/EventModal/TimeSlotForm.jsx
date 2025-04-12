import React from 'react';
import { Button, Form, Input, Space, TimePicker, Modal } from 'antd';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { fromServerFormat, toServerFormat } from '../../../utils/dateUtils';

const TimeSlotForm = ({
  form,
  isEditing,
  modifiedSlots,
  setModifiedSlots,
  setDefaultEvents,
  queryClient,
  calendarApi,

}) => {
  const handleTimeSlotChange = (index, field, value) => {
    const timeSlots = form.getFieldValue('time_slots') || [];
    const newSlots = [...timeSlots];
    
    if (field === 'timeRange') {
      newSlots[index] = {
        ...newSlots[index],
        start: value?.[0] ? toServerFormat(value[0]) : null,
        end: value?.[1] ? toServerFormat(value[1]) : null
      };
    } else {
      newSlots[index] = {
        ...newSlots[index],
        [field]: value
      };
    }

    form.setFieldsValue({ time_slots: newSlots });
    
    if (newSlots[index]?.id && !modifiedSlots.includes(newSlots[index].id)) {
      setModifiedSlots([...modifiedSlots, newSlots[index].id]);
    }
  };

  return (
    <Form.Item label="时间段" required>
      <Form.List name="time_slots">
        {(fields, { add, remove }) => (
          <>
            {fields.map(({ key, name, ...restField }) => {
              const slot = form.getFieldValue(['time_slots', name]);
              const startTime = slot?.start ? fromServerFormat(slot.start) : null;
              const endTime = slot?.end ? fromServerFormat(slot.end) : null;

              return (
                <Space
                  key={key}
                  style={{ display: 'flex', marginBottom: 8 }}
                  align="baseline"
                >
                  <Form.Item
                    {...restField}
                    name={[name, 'timeRange']}
                    rules={[
                      {
                        required: true,
                        message: '请选择时间段',
                        validator: (_, value) => {
                          if (!value || !value[0] || !value[1]) {
                            return Promise.reject('请选择完整时间段');
                          }
                          return Promise.resolve();
                        }
                      }
                    ]}
                  >
                    <TimePicker.RangePicker
                      format="HH:mm"
                      minuteStep={15}
                      disabled={!isEditing}
                      value={[startTime, endTime]}
                      onChange={(value) => 
                        handleTimeSlotChange(name, 'timeRange', value)
                      }
                    />
                  </Form.Item>

                  <Form.Item
                    {...restField}
                    name={[name, 'description']}
                  >
                    <Input
                      placeholder="描述(可选)"
                      disabled={!isEditing}
                      onChange={(e) => 
                        handleTimeSlotChange(name, 'description', e.target.value)
                      }
                    />
                  </Form.Item>

                  {isEditing && (
                    <MinusCircleOutlined
                      onClick={() => {
                        if (slot?.id) {
                          Modal.confirm({
                            title: '确认删除',
                            content: '确定要删除这个时间段吗？',
                            onOk: async () => {
                              try {
                                await calendarApi.deleteTimeSlot(slot.id);
                                queryClient.invalidateQueries(['trials']);
                                remove(name);
                              } catch (error) {
                                console.error('删除时间段失败:', error);
                                Modal.error({
                                  title: '删除失败',
                                  content: error.message,
                                });
                              }
                            }
                          });
                        } else {
                          remove(name);
                        }
                      }}
                    />
                  )}
                </Space>
              );
            })}

            {isEditing && (
              <Form.Item>
                <Button
                  type="dashed"
                  onClick={() => {
                    add({
                      start: null,
                      end: null,
                      description: ''
                    });
                  }}
                  block
                  icon={<PlusOutlined />}
                >
                  添加时间段
                </Button>
              </Form.Item>
            )}
          </>
        )}
      </Form.List>
    </Form.Item>
  );
};

export default TimeSlotForm;
