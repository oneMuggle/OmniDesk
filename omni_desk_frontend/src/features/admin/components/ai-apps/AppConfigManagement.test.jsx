import { APP_NAME_OPTIONS, APP_NAME_LABELS } from './AppConfigManagement';

describe('AppConfigManagement APP_NAME_OPTIONS', () => {
  it('包含 smart_assistant 与 office_assistant 两个选项', () => {
    expect(APP_NAME_OPTIONS).toEqual(
      expect.arrayContaining([
        { label: '智能助手', value: 'smart_assistant' },
        { label: '办公助手', value: 'office_assistant' },
      ]),
    );
  });

  it('每个选项都有 label + value 字段且均为字符串', () => {
    for (const opt of APP_NAME_OPTIONS) {
      expect(opt).toHaveProperty('label');
      expect(opt).toHaveProperty('value');
      expect(typeof opt.label).toBe('string');
      expect(typeof opt.value).toBe('string');
      expect(opt.label.length).toBeGreaterThan(0);
      expect(opt.value.length).toBeGreaterThan(0);
    }
  });

  it('value 在选项之间唯一(无重复)', () => {
    const values = APP_NAME_OPTIONS.map((o) => o.value);
    expect(new Set(values).size).toBe(values.length);
  });
});

describe('AppConfigManagement APP_NAME_LABELS', () => {
  it('office_assistant 映射到 办公助手', () => {
    expect(APP_NAME_LABELS.office_assistant).toBe('办公助手');
  });

  it('smart_assistant 映射到 智能助手 (向后兼容)', () => {
    expect(APP_NAME_LABELS.smart_assistant).toBe('智能助手');
  });

  it('未知 app_name 返回原值(表格 render 兜底行为)', () => {
    // 模拟表格列 render: APP_NAME_LABELS[text] || text
    const fallback = (text) => APP_NAME_LABELS[text] || text;
    expect(fallback('unknown_app')).toBe('unknown_app');
    expect(fallback('smart_assistant')).toBe('智能助手');
    expect(fallback('office_assistant')).toBe('办公助手');
  });
});
