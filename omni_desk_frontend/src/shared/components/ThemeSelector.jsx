import { Dropdown } from 'antd';
import { BgColorsOutlined, CheckOutlined } from '@ant-design/icons';
import { useTheme } from '../context/ThemeContext';

function ThemeSelector() {
  const { themeId, themeOptions, setTheme } = useTheme();

  const menuItems = themeOptions.map(scheme => ({
    key: scheme.id,
    label: (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '2px 0',
        }}
      >
        <span
          style={{
            display: 'inline-block',
            width: 14,
            height: 14,
            borderRadius: 3,
            background: scheme.primary,
            border: '1px solid rgba(0,0,0,0.1)',
          }}
        />
        <span>{scheme.name}</span>
        {themeId === scheme.id && (
          <CheckOutlined style={{ marginLeft: 'auto', color: 'var(--color-primary)' }} />
        )}
      </div>
    ),
    onClick: () => setTheme(scheme.id),
  }));

  return (
    <Dropdown
      menu={{
        items: menuItems,
        selectable: false,
        style: { minWidth: 140 },
      }}
      trigger={['click']}
      placement="bottomRight"
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          cursor: 'pointer',
          padding: '4px 8px',
          borderRadius: 6,
        }}
      >
        <BgColorsOutlined />
        <span>主题</span>
      </div>
    </Dropdown>
  );
}

export default ThemeSelector;
