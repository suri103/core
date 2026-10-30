import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BookingSuccess from '../BookingSuccess';

describe('BookingSuccess Page', () => {
  it('renders the verified booking details passed in router state', () => {
    render(
      <MemoryRouter initialEntries={[{
        pathname: '/book/success',
        state: {
          pageTitle: 'Bright Smiles Booking',
          logoUrl: 'https://example.com/logo.png',
          confirmationCode: 'ABC12345',
          requestedDate: '2026-07-01',
          requestedTime: '09:00:00',
        },
      }]}>
        <BookingSuccess />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: /booking requested/i })).toBeInTheDocument();
    expect(screen.getByText('Bright Smiles Booking')).toBeInTheDocument();
    expect(screen.getByText('ABC12345')).toBeInTheDocument();
    expect(screen.getByText('09:00')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /add to calendar/i })).not.toBeInTheDocument();
  });

  it('uses safe generic copy when navigation state is absent', () => {
    render(
      <MemoryRouter initialEntries={['/book/success']}>
        <BookingSuccess />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Booking details unavailable' })).toBeInTheDocument();
    expect(screen.getByText(/no verified booking details were provided/i)).toBeInTheDocument();
    expect(screen.queryByText(/request verified/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /return home/i })).toBeInTheDocument();
  });
});
