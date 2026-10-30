import React from 'react';
import { sanitizeHtml, sanitizeText, sanitizePatientNote } from '@/lib/sanitize';
import { cn } from '@/lib/utils';
import type { ClassValue } from 'clsx';

interface SanitizedContentProps extends React.HTMLAttributes<HTMLElement> {
  /**
   * The raw HTML or text content to sanitize and display
   */
  content: string;
  
  /**
   * Type of sanitization to apply
   * - 'html': Sanitize HTML tags but allow safe formatting
   * - 'text': Escape all HTML entities (plain text)
   * - 'clinical': Specialized sanitization for clinical notes
   */
  type?: 'html' | 'text' | 'clinical';
  
  /**
   * Element type to render (div, p, span, etc.)
   */
  as?: React.ElementType;
  
  /**
   * Fallback content if content is empty
   */
  fallback?: string;
}

/**
 * SanitizedContent - Safe content display component
 * 
 * This component ensures all user-generated content is properly sanitized
 * before rendering to prevent XSS attacks. It's specifically designed for
 * displaying patient notes, clinical data, and other user-generated content.
 * 
 * @example
 * // Display HTML content with safe tags
 * <SanitizedContent content={note.html} type="html" />
 * 
 * // Display plain text (escape all HTML)
 * <SanitizedContent content={patient.name} type="text" />
 * 
 * // Display clinical notes with specialized sanitization
 * <SanitizedContent content={note.content} type="clinical" />
 */
export function SanitizedContent({
  content,
  type = 'text',
  className,
  as: Component = 'div',
  fallback = '—',
  ...props
}: SanitizedContentProps) {
  // Return fallback for empty content
  if (!content || content.trim() === '') {
    return <Component className={cn(className)} {...props}>{fallback}</Component>;
  }

  // Apply appropriate sanitization based on type
  let sanitizedContent: string;
  switch (type) {
    case 'html':
      sanitizedContent = sanitizeHtml(content);
      break;
    case 'clinical':
      sanitizedContent = sanitizePatientNote(content);
      break;
    case 'text':
    default:
      sanitizedContent = sanitizeText(content);
      break;
  }

  // For text type, render as plain text (no dangerouslySetInnerHTML)
  if (type === 'text') {
    return (
      <Component className={cn(className)} {...props}>
        {sanitizedContent}
      </Component>
    );
  }

  // For html and clinical types, use dangerouslySetInnerHTML with sanitized content
  return (
    <Component
      className={cn(className)}
      dangerouslySetInnerHTML={{ __html: sanitizedContent }}
      {...props}
    />
  );
}

/**
 * SanitizedNote - Specialized component for clinical notes
 * Pre-configured for displaying patient clinical notes safely
 */
interface SanitizedNoteProps extends Omit<SanitizedContentProps, 'type' | 'as'> {
  content: string;
}

export function SanitizedNote({ content, className, fallback, ...props }: SanitizedNoteProps) {
  return (
    <SanitizedContent
      content={content}
      type="clinical"
      as="div"
      className={cn('prose prose-sm max-w-none', className as ClassValue)}
      fallback={fallback}
      {...(props as React.HTMLAttributes<HTMLDivElement>)}
    />
  );
}

/**
 * SanitizedHtml - Specialized component for HTML content
 * Pre-configured for displaying user-generated HTML safely
 */
interface SanitizedHtmlProps extends Omit<SanitizedContentProps, 'type' | 'as'> {
  content: string;
}

export function SanitizedHtml({ content, className, fallback, ...props }: SanitizedHtmlProps) {
  return (
    <SanitizedContent
      content={content}
      type="html"
      as="div"
      className={cn('prose prose-sm max-w-none', className as ClassValue)}
      fallback={fallback}
      {...(props as React.HTMLAttributes<HTMLDivElement>)}
    />
  );
}

/**
 * SanitizedText - Specialized component for plain text
 * Pre-configured for displaying user input as plain text
 */
interface SanitizedTextProps extends Omit<SanitizedContentProps, 'type' | 'as'> {
  content: string;
  as?: React.ElementType;
}

export function SanitizedText({ content, className, fallback, as: AsComponent = 'span', ...props }: SanitizedTextProps) {
  return (
    <SanitizedContent
      content={content}
      type="text"
      as={AsComponent}
      className={className}
      fallback={fallback}
      {...(props as React.HTMLAttributes<HTMLElement>)}
    />
  );
}
