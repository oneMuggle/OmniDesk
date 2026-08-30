import { safeDisplay } from '../../components/ToolCallCard';

describe('ToolCallCard 安全显示', () => {
  test('脱敏邮箱、手机号和身份证号', () => {
    const value = '邮箱 a@example.com，手机 13812345678，身份证 110105199001011234';
    const displayed = safeDisplay(value);
    expect(displayed).not.toContain('a@example.com');
    expect(displayed).not.toContain('13812345678');
    expect(displayed).not.toContain('110105199001011234');
    expect(displayed.match(/\[已隐藏\]/g)).toHaveLength(3);
  });

  test('不脱敏更长数字串中的手机号和身份证号', () => {
    const displayed = safeDisplay('138123456789 1101051990010112345 110105199001011234X9');
    expect(displayed).toContain('138123456789');
    expect(displayed).toContain('1101051990010112345');
    expect(displayed).toContain('110105199001011234X9');
  });

  test('过滤 API、private、access 和 session 敏感字段', () => {
    const displayed = safeDisplay({ api_key: 'a', private_key: 'b', access_token: 'c', session_id: 'd', visible: 'ok' });
    expect(displayed).toContain('visible: ok');
    expect(displayed).not.toMatch(/api_key|private_key|access_token|session_id/);
  });
});
