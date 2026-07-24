import React, { useState } from 'react';
import { Tabs, Table, Typography } from 'antd';
import ReactMarkdown from 'react-markdown';

const { Text } = Typography;

/**
 * 文件预览组件 — 根据 mimeType 自动选择展示方式
 *
 * Excel/CSV → Ant Design Table（支持多 Sheet 切换 + 分页）
 * Word/PDF  → ReactMarkdown
 *
 * @param {object}   props.data     预览数据（含 sheets 或 markdown）
 * @param {string}   props.mimeType 文件 MIME 类型
 */
const PreviewSection = ({ data, mimeType }) => {
  const [activeSheet, setActiveSheet] = useState(0);

  if (!data || !mimeType) {
    return <Text type="secondary">无预览数据</Text>;
  }

  // ── Excel / CSV：表格展示 ──────────────────────────────
  if (mimeType.includes('spreadsheet') || mimeType.includes('csv')) {
    const sheets = data.sheets || [];

    if (sheets.length === 0) {
      return <Text type="secondary">无数据</Text>;
    }

    const currentSheet = sheets[activeSheet] || sheets[0];
    const headers = currentSheet.headers || [];
    const rows = currentSheet.data || [];

    const columns = headers.map((header, index) => ({
      title: header || `列 ${index + 1}`,
      dataIndex: `col_${index}`,
      key: `col_${index}`,
      ellipsis: true,
    }));

    const dataSource = rows.map((row, rowIndex) => {
      const record = { key: rowIndex };
      row.forEach((cell, colIndex) => {
        record[`col_${colIndex}`] = cell;
      });
      return record;
    });

    // 多 Sheet 时构造 Tabs items
    const tabItems = sheets.length > 1
      ? sheets.map((sheet, index) => ({
          key: String(index),
          label: sheet.name || `Sheet ${index + 1}`,
        }))
      : [];

    return (
      <div className="preview-section">
        {tabItems.length > 0 && (
          <Tabs
            activeKey={String(activeSheet)}
            onChange={(key) => setActiveSheet(Number(key))}
            items={tabItems}
          />
        )}

        <Table
          columns={columns}
          dataSource={dataSource}
          pagination={{
            pageSize: 50,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 行`,
          }}
          scroll={{ x: 'max-content' }}
          size="small"
        />

        <div style={{ marginTop: 8 }}>
          <Text type="secondary">
            共 {currentSheet.row_count ?? rows.length} 行，{currentSheet.column_count ?? headers.length} 列
          </Text>
        </div>
      </div>
    );
  }

  // ── Word / PDF：Markdown 展示 ─────────────────────────
  if (mimeType.includes('word') || mimeType.includes('pdf')) {
    return (
      <div className="preview-section markdown-preview">
        <ReactMarkdown>{data.markdown || ''}</ReactMarkdown>
      </div>
    );
  }

  return <Text type="secondary">不支持的文件类型</Text>;
};

export default PreviewSection;
