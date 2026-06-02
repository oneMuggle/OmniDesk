import React from 'react';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';

describe('ExternalLinkManagementPage', () => {
  it('should be importable', async () => {
    const ExternalLinkManagementPage = await import('./ExternalLinkManagementPage');
    expect(ExternalLinkManagementPage).toBeDefined();
  });
});
