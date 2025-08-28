import React from 'react';
import { Form, Select, Spin, Modal } from 'antd';
import { getTrials } from '../api/trials';
import { trialApi } from '../api/trialApi';

const TrialSelector = ({
  trials,
  isTrialsLoading,
  form,
  onTrialSelect
}) => {
  return (
    <Form.Item label="试验项目" required name="trial">
      <Select
        showSearch
        placeholder="搜索试验项目"
        filterOption={(input, option) =>
          `${option.label} ${option.value}`.toLowerCase().includes(input.toLowerCase())
        }
        options={trials.map(trial => ({
          value: trial.id,
          label: `${trial.title} (${trial.client})`,
          trialData: trial
        }))}
        optionFilterProp="label"
        onSearch={value => {
          getTrials({ search: value });
        }}
        loading={isTrialsLoading}
        onChange={async (value, option) => {
          if (!option) {
            onTrialSelect(null);
            form.setFieldsValue({ time_slots: [] });
            return;
          }
          onTrialSelect(option.trialData);
          
          try {
            const slots = await trialApi.fetchTimeSlotsByTrial(value);
            if (!slots || slots.length === 0) {
              console.warn('获取到空时间段数组', { trialId: value });
              form.setFieldsValue({ time_slots: [] });
              return;
            }
            
            const validSlots = slots.filter(slot => 
              slot.id && slot.start && slot.end
            );
            
            if (validSlots.length !== slots.length) {
              console.warn('过滤掉无效时间段', {
                trialId: value,
                total: slots.length,
                valid: validSlots.length
              });
            }
            
            form.setFieldsValue({ 
              time_slots: validSlots.map(slot => ({
                id: slot.id,
                start: slot.start,
                end: slot.end,
                description: slot.description || ''
              }))
            });
          } catch (error) {
            console.error('获取时间段失败:', error);
            Modal.warning({
              title: '获取时间段失败',
              content: `无法获取试验的时间段数据`,
            });
            form.setFieldsValue({ time_slots: [] });
          }
        }}
      />
    </Form.Item>
  );
};

export default TrialSelector;