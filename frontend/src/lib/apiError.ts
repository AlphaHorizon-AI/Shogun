export const apiDetailMessage = (detail: unknown): string => {
  if (typeof detail === 'string') return detail.trim();
  if (Array.isArray(detail)) {
    return detail.map(apiDetailMessage).filter(Boolean).join('\n');
  }
  if (detail && typeof detail === 'object') {
    const record = detail as Record<string, unknown>;
    const message = apiDetailMessage(record.msg ?? record.message ?? record.detail ?? record.error);
    const location = Array.isArray(record.loc)
      ? record.loc.filter((part) => part !== 'body').map(String).join('.')
      : '';
    if (message) return location ? `${location}: ${message}` : message;
    try {
      return JSON.stringify(detail);
    } catch {
      return '';
    }
  }
  return detail == null ? '' : String(detail);
};

export const apiErrorMessage = (error: unknown, fallback: string): string => {
  const candidate = error as {
    message?: unknown;
    response?: { data?: { detail?: unknown; error?: unknown } };
  } | null;
  const responseMessage = apiDetailMessage(
    candidate?.response?.data?.detail ?? candidate?.response?.data?.error
  );
  return responseMessage || apiDetailMessage(candidate?.message) || fallback;
};
