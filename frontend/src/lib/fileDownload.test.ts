import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';
import { downloadAuthenticatedFile, extractBlobErrorMessage } from './fileDownload';

describe('fileDownload utility', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('downloads file using axios blob request and creates anchor link', async () => {
    const mockBlob = new Blob(['mock content'], { type: 'application/zip' });
    const getSpy = vi.spyOn(axios, 'get').mockResolvedValue({
      data: mockBlob,
      headers: {
        'content-disposition': 'attachment; filename="shogun_export_test.zip"',
      },
    });

    const createObjectURL = vi.fn().mockReturnValue('blob:http://localhost/test-uuid');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL });

    const createdLink: any = {
      href: '',
      download: '',
      style: {},
      click: vi.fn(),
    };
    const appendChild = vi.fn();
    const removeChild = vi.fn();

    vi.stubGlobal('document', {
      createElement: vi.fn().mockReturnValue(createdLink),
      body: {
        appendChild,
        removeChild,
      },
    });

    await downloadAuthenticatedFile('/api/v1/memory/export/exp_1/download', 'fallback.zip');

    expect(getSpy).toHaveBeenCalledWith('/api/v1/memory/export/exp_1/download', {
      responseType: 'blob',
    });
    expect(createObjectURL).toHaveBeenCalledWith(mockBlob);
    expect(createdLink.click).toHaveBeenCalledOnce();
    expect(createdLink.download).toBe('shogun_export_test.zip');
    expect(createdLink.href).toBe('blob:http://localhost/test-uuid');
    expect(appendChild).toHaveBeenCalledWith(createdLink);
    expect(removeChild).toHaveBeenCalledWith(createdLink);
  });

  it('falls back to default filename when Content-Disposition is omitted', async () => {
    const mockBlob = new Blob(['test']);
    vi.spyOn(axios, 'get').mockResolvedValue({
      data: mockBlob,
      headers: {},
    });

    const createObjectURL = vi.fn().mockReturnValue('blob:http://localhost/fallback-uuid');
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL: vi.fn() });

    const createdLink: any = {
      href: '',
      download: '',
      style: {},
      click: vi.fn(),
    };

    vi.stubGlobal('document', {
      createElement: vi.fn().mockReturnValue(createdLink),
      body: {
        appendChild: vi.fn(),
        removeChild: vi.fn(),
      },
    });

    await downloadAuthenticatedFile('/api/v1/workspace/download?path=notes.txt', 'notes.txt');

    expect(createdLink.download).toBe('notes.txt');
  });

  it('extracts detail message from Blob error response', async () => {
    const errorJson = JSON.stringify({ detail: 'Memory export job not found' });
    const errorBlob = new Blob([errorJson], { type: 'application/json' });
    const error = {
      response: {
        data: errorBlob,
      },
    };

    const message = await extractBlobErrorMessage(error, 'Default fallback');
    expect(message).toBe('Memory export job not found');
  });

  it('falls back to string detail or fallback message when not a JSON Blob', async () => {
    const plainError = {
      response: {
        data: { detail: 'Unauthorized' },
      },
    };
    expect(await extractBlobErrorMessage(plainError, 'Fallback')).toBe('Unauthorized');

    const networkError = new Error('Network failure');
    expect(await extractBlobErrorMessage(networkError, 'Fallback')).toBe('Network failure');

    const emptyError = {};
    expect(await extractBlobErrorMessage(emptyError, 'Fallback')).toBe('Fallback');
  });
});
