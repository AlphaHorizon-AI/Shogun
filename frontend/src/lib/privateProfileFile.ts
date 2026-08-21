const PRIVATE_PROFILE_SUFFIX = '.shogun-profile.json';

export const MAX_PRIVATE_PROFILE_FILE_BYTES = 2_000_000;

export type JsonFileSaveResult = 'saved' | 'cancelled';

type WritableFileHandle = {
  write: (data: Blob) => Promise<void>;
  close: () => Promise<void>;
};

type SaveFileHandle = {
  createWritable: () => Promise<WritableFileHandle>;
};

type SaveFilePicker = (options: {
  suggestedName: string;
  types: Array<{
    description: string;
    accept: Record<string, string[]>;
  }>;
}) => Promise<SaveFileHandle>;

export const privateProfileFilename = (suggestedName: unknown): string => {
  const raw = typeof suggestedName === 'string' ? suggestedName.trim() : '';
  const withoutSuffix = raw.replace(/\.shogun-profile\.json$/i, '').replace(/\.json$/i, '');
  const safeStem = Array.from(withoutSuffix)
    .filter((character) => character.charCodeAt(0) >= 32)
    .join('')
    .replace(/[<>:"/\\|?*]/g, '-')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/[-. ]+$/g, '')
    .replace(/^[-. ]+/g, '')
    .slice(0, 120);
  return `${safeStem || 'private-transformation-profile'}${PRIVATE_PROFILE_SUFFIX}`;
};

export const parsePrivateProfileDocument = (contents: string): Record<string, unknown> => {
  let parsed: unknown;
  try {
    parsed = JSON.parse(contents);
  } catch {
    throw new Error('The selected private profile file is not valid JSON.');
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('The selected private profile file must contain one JSON object.');
  }
  return parsed as Record<string, unknown>;
};

export const savePrivateProfileDocument = async (
  profileDocument: unknown,
  suggestedName: unknown,
): Promise<JsonFileSaveResult> => {
  const filename = privateProfileFilename(suggestedName);
  const blob = new Blob([`${JSON.stringify(profileDocument, null, 2)}\n`], {
    type: 'application/json',
  });
  const picker = (window as Window & { showSaveFilePicker?: SaveFilePicker }).showSaveFilePicker;

  if (picker) {
    let fileHandle: SaveFileHandle | null = null;
    try {
      fileHandle = await picker.call(window, {
        suggestedName: filename,
        types: [{
          description: 'Shogun private transformation profile',
          accept: { 'application/json': ['.json'] },
        }],
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return 'cancelled';
      // Some browsers expose the picker but reject it outside a secure context.
      // In that case, continue through the regular browser-download fallback.
    }
    if (fileHandle) {
      const writable = await fileHandle.createWritable();
      await writable.write(blob);
      await writable.close();
      return 'saved';
    }
  }

  const objectUrl = URL.createObjectURL(blob);
  try {
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = filename;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
  return 'saved';
};
