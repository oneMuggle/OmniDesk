jest.mock('../api/documents', () => ({
  __esModule: true,
  default: {
    getDocumentTemplates: jest.fn().mockResolvedValue({ data: { results: [] } }),
    uploadTemplate: jest.fn().mockResolvedValue({}),
    analyzeDocumentTemplate: jest.fn().mockResolvedValue({ data: { issues: [] } }),
    generateDocument: jest.fn().mockResolvedValue({ data: new Blob() }),
  },
}));

jest.mock('../../projects/api/projects', () => ({
  __esModule: true,
  default: {
    getAllProjects: jest.fn().mockResolvedValue({ data: { results: [] } }),
  },
}));

jest.mock('../../../shared/components/ChatInterface', () => function MockChatInterface() {
  return <div data-testid="chat">ChatInterface</div>;
});

import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import DocumentsPage from './DocumentsPage';

describe('DocumentsPage', () => {
  it('renders documents page', () => {
    render(
      <MemoryRouter>
        <DocumentsPage />
      </MemoryRouter>
    );
    expect(screen.getByTestId('chat')).toBeInTheDocument();
  });

  it('renders template management section', () => {
    render(
      <MemoryRouter>
        <DocumentsPage />
      </MemoryRouter>
    );
    expect(screen.getByText('上传新模板')).toBeInTheDocument();
    expect(screen.getByText('选择项目：')).toBeInTheDocument();
  });
});
