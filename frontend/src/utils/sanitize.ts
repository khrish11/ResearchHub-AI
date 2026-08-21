/**
 * Sanitization utilities for AI-generated content
 * 
 * Uses DOMPurify to sanitize HTML content and prevent XSS attacks.
 * This is particularly important for AI-generated content which may
 * contain malicious HTML/JavaScript.
 */

import DOMPurify from 'dompurify';

/**
 * Sanitize HTML content to prevent XSS attacks
 * 
 * @param html - The HTML string to sanitize
 * @returns Sanitized HTML string safe to render
 */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'code', 'pre'],
    ALLOWED_ATTR: ['href', 'title', 'target'],
    ALLOW_DATA_ATTR: false,
  });
}

/**
 * Sanitize plain text content (removes any HTML tags)
 * 
 * @param text - The text to sanitize
 * @returns Plain text with HTML tags removed
 */
export function sanitizeText(text: string): string {
  return DOMPurify.sanitize(text, { ALLOWED_TAGS: [] });
}

/**
 * Sanitize markdown content for safe rendering
 * 
 * @param markdown - The markdown string to sanitize
 * @returns Sanitized markdown string
 */
export function sanitizeMarkdown(markdown: string): string {
  // For markdown, we sanitize as text since markdown will be rendered
  // by a markdown renderer that should handle escaping
  return sanitizeText(markdown);
}
