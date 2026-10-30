import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AttachmentsList } from '../AttachmentsList';
import { patientApi } from '@/services/patientApi';

const toastMock = vi.hoisted(() => vi.fn());

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/services/patientApi', () => ({
  patientApi: {
    uploadAttachment: vi.fn(),
    deleteAttachment: vi.fn(),
  },
}));

const mockPatientApi = vi.mocked(patientApi);

const attachments = [
  {
    id: 'att-1',
    name: 'insurance-card.pdf',
    type: 'application/pdf',
    size: 1536,
    url: 'https://example.com/insurance-card.pdf',
    category: 'insurance' as const,
    uploadedAt: '2026-06-10',
    uploadedBy: 'staff-1',
    uploadedByName: 'Front Desk',
  },
  {
    id: 'att-2',
    name: 'bitewing.png',
    type: 'image/png',
    size: 2048,
    url: 'https://example.com/bitewing.png',
    category: 'xray' as const,
    uploadedAt: '2026-06-11',
    uploadedBy: 'staff-2',
    uploadedByName: 'Dental Assistant',
  },
  {
    id: 'att-3',
    name: 'consent-form.pdf',
    type: 'application/pdf',
    size: 512,
    url: 'https://example.com/consent-form.pdf',
    category: 'consent' as const,
    uploadedAt: '2026-06-12',
    uploadedBy: 'staff-3',
    uploadedByName: 'Coordinator',
  },
  {
    id: 'att-4',
    name: 'referral-note.pdf',
    type: 'application/pdf',
    size: 1024,
    url: 'https://example.com/referral-note.pdf',
    category: 'referral' as const,
    uploadedAt: '2026-06-13',
    uploadedBy: 'staff-4',
    uploadedByName: 'Office Manager',
  },
  {
    id: 'att-5',
    name: 'misc.txt',
    type: 'text/plain',
    size: 0,
    url: 'https://example.com/misc.txt',
    category: 'other' as const,
    uploadedAt: '2026-06-14',
    uploadedBy: 'staff-5',
    uploadedByName: 'Reception',
  },
];

describe('AttachmentsList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows the selected file state when a file is chosen', async () => {
    const user = userEvent.setup();

    const { container } = render(
      <AttachmentsList
        patientId="patient-1"
        attachments={[]}
        onUpload={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, new File(['hello'], 'xray.jpg', { type: 'image/jpeg' }));

    expect(screen.getByText('xray.jpg')).toBeInTheDocument();
    expect(screen.getByText(/Size: 5 Bytes/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /upload to patient record/i })).toBeEnabled();
  });

  it('renders attachments and deletes a selected file', async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();

    mockPatientApi.deleteAttachment.mockResolvedValue(undefined as never);

    render(
      <AttachmentsList
        patientId="patient-1"
        attachments={attachments}
        onUpload={vi.fn()}
        onDelete={onDelete}
      />,
    );

    expect(screen.getByText('insurance-card.pdf')).toBeInTheDocument();
    expect(screen.getByText('1.5 KB')).toBeInTheDocument();
    expect(screen.getByText('0 Bytes')).toBeInTheDocument();
    expect(screen.getByText('bitewing.png')).toBeInTheDocument();
    expect(screen.getByText('consent-form.pdf')).toBeInTheDocument();
    expect(screen.getByText('referral-note.pdf')).toBeInTheDocument();

    const buttons = screen.getAllByRole('button');
    await user.click(buttons[buttons.length - 1]);

    expect(mockPatientApi.deleteAttachment).toHaveBeenCalledWith('patient-1', 'att-5');
    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(toastMock).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'File Deleted' }),
    );
  });
});
