import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  sanitizeHtml,
  sanitizeText,
  sanitizeUrl,
  sanitizePatientNote,
  sanitizeJson,
  sanitizeEmail,
  sanitizePhone,
  createSanitizedHtml,
} from '../sanitize';
import {
  SanitizedContent,
  SanitizedHtml,
  SanitizedNote,
  SanitizedText,
} from '@/components/SanitizedContent';

describe('sanitize utilities', () => {
  it('sanitizes html, text, urls, and structured data', () => {
    expect(sanitizeHtml('<p>Hello <script>alert(1)</script><strong>world</strong></p>')).toContain('<strong>world</strong>');
    expect(sanitizeHtml('<p>Hello <script>alert(1)</script><strong>world</strong></p>')).not.toContain('script');
    expect(sanitizeText('<b>safe?</b>')).toBe('&lt;b&gt;safe?&lt;/b&gt;');
    expect(sanitizeUrl('https://example.com/path')).toBe('https://example.com/path');
    expect(sanitizeUrl('/relative/path')).toBe('/relative/path');
    expect(sanitizeUrl('javascript:alert(1)')).toBe('');
    expect(sanitizeUrl('')).toBe('');
    expect(sanitizePatientNote('<h1>Plan</h1><script>bad()</script>')).toContain('<h1>Plan</h1>');
    expect(sanitizeEmail('  Doctor@Example.com ')).toBe('doctor@example.com');
    expect(sanitizeEmail('not-an-email')).toBeNull();
    expect(sanitizePhone('+1 (555) 123-4567 ext. 9')).toBe('+155512345679');
    expect(createSanitizedHtml('<p>hello</p>')).toEqual({ __html: expect.any(String) });

    expect(
      sanitizeJson({
        name: '<b>Maya</b>',
        nested: { note: '<script>x</script><i>ok</i>' },
        count: 3,
        tags: ['keep'],
      }),
    ).toEqual({
      name: '&lt;b&gt;Maya&lt;/b&gt;',
      nested: { note: '&lt;script&gt;x&lt;/script&gt;&lt;i&gt;ok&lt;/i&gt;' },
      count: 3,
      tags: ['keep'],
    });
  });
});

describe('SanitizedContent components', () => {
  it('renders fallbacks and sanitized content across variants', () => {
    const { container, rerender } = render(<SanitizedContent content="" fallback="No data" />);
    expect(screen.getByText('No data')).toBeInTheDocument();

    rerender(<SanitizedContent content="<b>plain</b>" type="text" />);
    expect(screen.getByText('&lt;b&gt;plain&lt;/b&gt;')).toBeInTheDocument();

    rerender(<SanitizedContent content="<p>Hello <strong>team</strong></p>" type="html" />);
    expect(container.querySelector('p')?.innerHTML).toContain('<strong>team</strong>');

    rerender(<SanitizedContent content="<h1>Plan</h1><script>bad()</script>" type="clinical" />);
    expect(container.querySelector('div')?.innerHTML).toContain('<h1>Plan</h1>');

    rerender(<SanitizedNote content="<p>Clinical note</p>" />);
    expect(screen.getByText('Clinical note')).toBeInTheDocument();

    rerender(<SanitizedHtml content="<p>HTML note</p>" />);
    expect(screen.getByText('HTML note')).toBeInTheDocument();

    rerender(<SanitizedText content="Plain text" />);
    expect(screen.getByText('Plain text')).toBeInTheDocument();
  });
});
