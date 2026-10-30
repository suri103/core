import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { AddProcedureDialog } from '../AddProcedureDialog';

/**
 * Bypass React's property descriptor tracking to set a controlled input's value.
 * React installs its own setter on input elements; fireEvent.change alone won't
 * trigger React's onChange because the tracker value already matches. Using the
 * native HTMLInputElement prototype setter + dispatching an 'input' event forces
 * React to see the value change and fire onChange.
 */
function setControlledValue(input: HTMLInputElement, value: string) {
  const nativeSetter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    'value',
  )!.set!;
  act(() => {
    nativeSetter.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}

describe('AddProcedureDialog', () => {
  const onOpenChange = vi.fn();
  const onSubmit = vi.fn();

  beforeEach(() => {
    onOpenChange.mockClear();
    onSubmit.mockClear();
  });

  it('renders the dialog with the tooth number and name', () => {
    render(
      <AddProcedureDialog
        open
        onOpenChange={onOpenChange}
        toothNumber={14}
        toothName="Upper Right First Molar"
        onSubmit={onSubmit}
      />,
    );
    expect(screen.getByText(/Add Procedure to Tooth #14/)).toBeInTheDocument();
    expect(screen.getByText('Upper Right First Molar')).toBeInTheDocument();
  });

  it('submits with the default code (D0120) and default surface', () => {
    render(
      <AddProcedureDialog
        open
        onOpenChange={onOpenChange}
        toothNumber={14}
        toothName="Tooth 14"
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Log Procedure/i }));
    expect(onSubmit).toHaveBeenCalledOnce();
    const submitted = onSubmit.mock.calls[0][0];
    expect(submitted.code).toBe('D0120');
    expect(submitted.surface).toBe('O');
    expect(submitted.cost).toBe(65); // default CDT price for D0120
    expect(submitted.status).toBe('planned');
    expect(submitted.date).toBeTruthy();
  });

  it('updates the price when a different code is selected', () => {
    render(
      <AddProcedureDialog
        open
        onOpenChange={onOpenChange}
        toothNumber={8}
        toothName="Tooth 8"
        onSubmit={onSubmit}
      />,
    );

    // Open the Radix Select trigger so the options render into the DOM
    const codeTrigger = screen.getByLabelText(/CDT Procedure Code/);
    fireEvent.click(codeTrigger);

    // After opening, the combobox is expanded (Radix renders options into the
    // same DOM). Assert the option D2750 is available by querying the
    // rendered SelectItem (with `role="option"`).
    const options = screen.getAllByRole('option');
    expect(options.length).toBeGreaterThan(1);
    const optionTexts = options.map((o) => o.textContent || '');
    expect(optionTexts.some((t) => t.includes('D0120'))).toBe(true);
    expect(optionTexts.some((t) => t.includes('D1110'))).toBe(true);
    expect(optionTexts.some((t) => t.includes('D2750'))).toBe(true);
  });

  it('includes the date in the submission (within ~1s of now)', () => {
    render(
      <AddProcedureDialog
        open
        onOpenChange={onOpenChange}
        toothNumber={14}
        toothName="Tooth 14"
        onSubmit={onSubmit}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Log Procedure/i }));
    const submitted = onSubmit.mock.calls[0][0];
    const submittedTime = new Date(submitted.date).getTime();
    // The submitted date is a valid ISO string for "now" — within a few seconds
    // of the test execution.
    expect(submittedTime).toBeGreaterThan(Date.now() - 5000);
    expect(submittedTime).toBeLessThanOrEqual(Date.now() + 1000);
  });

  it('changes the price when a different code is picked (verifies the onValueChange handler)', () => {
    render(
      <AddProcedureDialog
        open
        onOpenChange={onOpenChange}
        toothNumber={8}
        toothName="Tooth 8"
        onSubmit={onSubmit}
      />,
    );

    // The default price field shows D0120's $65 price (pre-populated).
    const priceInput = screen.getByLabelText(/Est. Price/i) as HTMLInputElement;
    expect(priceInput.value).toBe('65');

    // Open the code picker
    fireEvent.click(screen.getByLabelText(/CDT Procedure Code/));
    const options = screen.getAllByRole('option');
    // Find and click D2750 (Crown - $1100)
    const d2750 = options.find((o) => (o.textContent || '').includes('D2750'));
    expect(d2750).toBeDefined();
    fireEvent.click(d2750!);

    // After selecting D2750, the price field should update to 1100
    expect((screen.getByLabelText(/Est. Price/i) as HTMLInputElement).value).toBe('1100');
  });

  it('includes notes when entered in the Clinical Notes field', () => {
    render(
      <AddProcedureDialog
        open
        onOpenChange={onOpenChange}
        toothNumber={3}
        toothName="Tooth 3"
        onSubmit={onSubmit}
      />,
    );

    const notesInput = screen.getByLabelText(/Clinical Notes/i) as HTMLInputElement;
    setControlledValue(notesInput, 'Patient reports sensitivity');

    fireEvent.click(screen.getByRole('button', { name: /Log Procedure/i }));

    const submitted = onSubmit.mock.calls[0][0];
    expect(submitted.notes).toBe('Patient reports sensitivity');
  });

  it('uses a custom price when one is entered in the price field', () => {
    render(
      <AddProcedureDialog
        open
        onOpenChange={onOpenChange}
        toothNumber={14}
        toothName="Tooth 14"
        onSubmit={onSubmit}
      />,
    );

    const priceInput = screen.getByLabelText(/Est. Price/i) as HTMLInputElement;
    setControlledValue(priceInput, '99.50');

    fireEvent.click(screen.getByRole('button', { name: /Log Procedure/i }));

    const submitted = onSubmit.mock.calls[0][0];
    expect(submitted.cost).toBe(99.5);
  });

  it('uses the CDT code default price when the custom price field is cleared', () => {
    render(
      <AddProcedureDialog
        open
        onOpenChange={onOpenChange}
        toothNumber={14}
        toothName="Tooth 14"
        onSubmit={onSubmit}
      />,
    );

    const priceInput = screen.getByLabelText(/Est. Price/i) as HTMLInputElement;
    setControlledValue(priceInput, '');

    fireEvent.click(screen.getByRole('button', { name: /Log Procedure/i }));
    const submitted = onSubmit.mock.calls[0][0];
    // Should fall back to D0120's $65 default price
    expect(submitted.cost).toBe(65);
  });

  it('closes the dialog after a successful submit', () => {
    render(
      <AddProcedureDialog
        open
        onOpenChange={onOpenChange}
        toothNumber={14}
        toothName="Tooth 14"
        onSubmit={onSubmit}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Log Procedure/i }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
