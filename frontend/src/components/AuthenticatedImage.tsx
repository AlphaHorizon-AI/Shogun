import { useEffect, useState, type ImgHTMLAttributes } from 'react';
import axios from 'axios';

type AuthenticatedImageProps = Omit<ImgHTMLAttributes<HTMLImageElement>, 'src'> & {
  src: string;
  fallbackSrc?: string;
};

const isProtectedAsset = (src: string) =>
  src.startsWith('/uploads/') ||
  src.startsWith('/mado/screenshots/') ||
  src.startsWith('/ronin/screenshots/');

/** Loads protected same-origin images through axios so the control-plane token is attached. */
export function AuthenticatedImage({ src, fallbackSrc, onError, ...props }: AuthenticatedImageProps) {
  const [loadedAsset, setLoadedAsset] = useState<{ source: string; url: string } | null>(null);
  const protectedAsset = isProtectedAsset(src);
  const resolvedSrc = protectedAsset
    ? (loadedAsset?.source === src ? loadedAsset.url : fallbackSrc)
    : src;

  useEffect(() => {
    if (!protectedAsset) return;

    const controller = new AbortController();
    let objectUrl: string | undefined;

    axios.get<Blob>(src, {
      responseType: 'blob',
      signal: controller.signal,
    }).then((response) => {
      objectUrl = URL.createObjectURL(response.data);
      setLoadedAsset({ source: src, url: objectUrl });
    }).catch((error) => {
      if (!axios.isCancel(error)) setLoadedAsset(null);
    });

    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src, protectedAsset]);

  if (!resolvedSrc) return null;

  return (
    <img
      {...props}
      src={resolvedSrc}
      onError={(event) => {
        if (protectedAsset && resolvedSrc !== fallbackSrc) setLoadedAsset(null);
        onError?.(event);
      }}
    />
  );
}
