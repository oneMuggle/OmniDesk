import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import CommunicationPage from './CommunicationPage';

jest.mock('../../../components/communication/PostList', () => () => <div>PostList</div>);

describe('CommunicationPage', () => {
  it('renders with PostList', () => {
    render(
      <MemoryRouter>
        <CommunicationPage />
      </MemoryRouter>
    );
    expect(screen.getByText('PostList')).toBeInTheDocument();
  });
});
