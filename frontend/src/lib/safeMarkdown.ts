/**
 * Render Shogun's intentionally small Markdown subset.
 *
 * Trust boundary: mandate text is user-controlled and is later passed to
 * dangerouslySetInnerHTML. Escape every HTML metacharacter before emitting
 * only the hard-coded tags below. Raw HTML is deliberately unsupported.
 */
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function renderMarkdown(md: string): string {
  return escapeHtml(md)
    .replace(/^### (.+)$/gm, '<h3 class="text-sm font-bold text-shogun-gold mt-4 mb-1">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-base font-bold text-shogun-gold mt-5 mb-2">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-lg font-bold text-shogun-gold mt-6 mb-2">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-shogun-text">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^- (.+)$/gm, '<li class="ml-4 text-sm text-[#c0c0c0] list-disc">$1</li>')
    .replace(/^---$/gm, '<hr class="border-shogun-border my-3" />')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>');
}
