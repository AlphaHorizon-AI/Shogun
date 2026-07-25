import { describe, expect, it } from 'vitest';

import { renderMarkdown } from './safeMarkdown';

describe('renderMarkdown trust boundary', () => {
  it.each([
    '<script>alert(1)</script>',
    '<img src=x onerror=alert(1)>',
    '<svg onload=alert(1)>',
    '<iframe srcdoc="<script>alert(1)</script>"></iframe>',
    '<a href="javascript:alert(1)">click</a>',
  ])('renders malicious HTML as inert text: %s', payload => {
    const rendered = renderMarkdown(payload);

    expect(rendered).not.toMatch(
      /<(script|img|svg|iframe|a)\b[^>]*(on\w+\s*=|href\s*=\s*["']?\s*javascript:)?/i,
    );
    expect(rendered).toContain('&lt;');
    expect(rendered).toContain('&gt;');
  });

  it('preserves the intentionally supported Markdown subset', () => {
    const rendered = renderMarkdown([
      '# Heading',
      '',
      '## Subheading',
      '',
      '**Bold**',
      '',
      '*Italic*',
      '',
      '- Item one',
      '- Item two',
      '',
      '---',
    ].join('\n'));

    expect(rendered).toContain('<h1');
    expect(rendered).toContain('<h2');
    expect(rendered).toContain('<strong');
    expect(rendered).toContain('<em>');
    expect(rendered).toContain('<li');
    expect(rendered).toContain('<hr');
  });

  it('escapes ampersands, quotes, and apostrophes before formatting', () => {
    expect(renderMarkdown(`"Rock & Roll's"`)).toBe('&quot;Rock &amp; Roll&#39;s&quot;');
  });
});
