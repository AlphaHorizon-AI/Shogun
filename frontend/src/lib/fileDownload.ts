import axios from 'axios';

/**
 * Downloads a file from an authenticated API endpoint using axios so that
 * the control-plane infrastructure token is automatically included.
 */
export async function downloadAuthenticatedFile(
  url: string,
  defaultFilename: string,
  fallbackMimeType?: string,
): Promise<void> {
  const response = await axios.get<Blob>(url, {
    responseType: 'blob',
  });

  let filename = defaultFilename;
  const disposition = response.headers?.['content-disposition'] || response.headers?.['Content-Disposition'];
  if (typeof disposition === 'string') {
    const utf8Match = /filename\*=UTF-8''([^;\n]*)/i.exec(disposition);
    if (utf8Match && utf8Match[1]) {
      try {
        filename = decodeURIComponent(utf8Match[1].trim());
      } catch {
        filename = utf8Match[1].trim();
      }
    } else {
      const basicMatch = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/i.exec(disposition);
      if (basicMatch && basicMatch[1]) {
        filename = basicMatch[1].replace(/['"]/g, '').trim();
      }
    }
  }

  const blob = fallbackMimeType && !(response.data instanceof Blob && response.data.type)
    ? new Blob([response.data], { type: fallbackMimeType })
    : response.data;

  if (typeof document === 'undefined') return;

  const objectUrl = URL.createObjectURL(blob);
  try {
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = filename;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } finally {
    setTimeout(() => URL.revokeObjectURL(objectUrl), 2000);
  }
}

/**
 * Extracts a human-readable error message from an axios error whose responseType was 'blob'.
 */
export async function extractBlobErrorMessage(error: any, fallbackMessage: string): Promise<string> {
  if (error?.response?.data instanceof Blob) {
    try {
      const text = await error.response.data.text();
      const parsed = JSON.parse(text);
      return parsed.detail || parsed.message || fallbackMessage;
    } catch {
      // Not JSON
    }
  }
  return error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallbackMessage;
}
