import React from 'react';
import { render, fireEvent, screen } from '@testing-library/react';
import FileAttachmentInput, { validateFile } from '../FileAttachmentInput';
import { ConfigProvider } from 'antd';

const renderWithProvider = (ui) => render(<ConfigProvider>{ui}</ConfigProvider>);

describe('validateFile', () => {
  test('accepts supported extension', () => {
    expect(validateFile({ name: '合同.docx', size: 100 }).ok).toBe(true);
  });
  test('rejects .doc', () => {
    expect(validateFile({ name: '旧版.doc', size: 100 }).ok).toBe(false);
  });
  test('rejects over 10MB', () => {
    expect(validateFile({ name: '大.pdf', size: 11 * 1024 * 1024 }).ok).toBe(false);
  });
});

describe('FileAttachmentInput', () => {
  test('renders selected file chip and remove button', () => {
    const file = new File(['abc'], '合同.docx', { type: 'application/octet-stream' });
    renderWithProvider(<FileAttachmentInput value={file} onChange={() => {}} />);
    expect(screen.getByText('合同.docx')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /移除/ }));
  });
});
