import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PwaInstallPrompt } from '../PwaInstallPrompt';

function dispatchInstallPrompt(outcome: 'accepted' | 'dismissed' = 'accepted') {
  const prompt = vi.fn().mockResolvedValue(undefined);
  const event = Object.assign(new Event('beforeinstallprompt'), {
    prompt,
    userChoice: Promise.resolve({ outcome, platform: 'web' }),
  });

  act(() => window.dispatchEvent(event));
  return prompt;
}

describe('PwaInstallPrompt', () => {
  it('offers installation and invokes the browser prompt', async () => {
    render(<PwaInstallPrompt />);
    const prompt = dispatchInstallPrompt();

    fireEvent.click(screen.getByRole('button', { name: 'Install' }));

    await waitFor(() => expect(prompt).toHaveBeenCalledOnce());
    await waitFor(() => expect(screen.queryByLabelText('Install CoreDent')).not.toBeInTheDocument());
  });

  it('can be dismissed without invoking installation', () => {
    render(<PwaInstallPrompt />);
    const prompt = dispatchInstallPrompt();

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss install prompt' }));

    expect(prompt).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('Install CoreDent')).not.toBeInTheDocument();
  });

  it('stays hidden when no browser install prompt is available', () => {
    render(<PwaInstallPrompt />);
    expect(screen.queryByLabelText('Install CoreDent')).not.toBeInTheDocument();
  });
});
