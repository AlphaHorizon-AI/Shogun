import { useEffect, useRef, useState } from 'react';
import axios from 'axios';

export interface ChatGPTSignIn {
  providerId: string;
  flow_id: string;
  authorization_url: string;
  callback_warning?: string;
}

interface Props {
  flow: ChatGPTSignIn;
  onComplete: (message: string) => void;
  onCancel: () => void;
}

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error) && typeof error.response?.data?.detail === 'string') {
    return error.response.data.detail;
  }
  return 'Could not complete this request. Try again.';
}

export default function ChatGPTOAuthPanel({ flow, onComplete, onCancel }: Props) {
  const [callbackUrl, setCallbackUrl] = useState('');
  const [message, setMessage] = useState('Complete ChatGPT sign-in in your browser.');
  const [busy, setBusy] = useState(false);
  const [retired, setRetired] = useState(false);
  const complete = useRef(onComplete);
  useEffect(() => { complete.current = onComplete; }, [onComplete]);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const deadline = Date.now() + 600_000;
    const poll = async () => {
      try {
        const response = await axios.get(`/api/v1/model-providers/${flow.providerId}/oauth/status`, {
          params: { flow_id: flow.flow_id },
        });
        if (!active) return;
        const result = response.data.data;
        if (result.status === 'success') {
          setCallbackUrl('');
          complete.current(result.message || 'ChatGPT connected.');
          return;
        }
        if (result.status !== 'pending') {
          setCallbackUrl('');
          setRetired(true);
          setMessage(result.message || 'This sign-in ended. Start again.');
          return;
        }
      } catch {
        if (active) setMessage('Waiting for Shogun to respond. Your sign-in link remains available.');
      }
      if (active && Date.now() < deadline) timer = setTimeout(poll, 1500);
      else if (active) {
        setCallbackUrl('');
        setRetired(true);
        setMessage('Sign-in expired. Close this panel and start again.');
      }
    };
    timer = setTimeout(poll, 1500);
    return () => { active = false; clearTimeout(timer); };
  }, [flow.providerId, flow.flow_id]);

  const finish = async () => {
    setBusy(true);
    try {
      const response = await axios.post(`/api/v1/model-providers/${flow.providerId}/oauth/complete`, {
        flow_id: flow.flow_id, callback_url: callbackUrl,
      });
      setCallbackUrl('');
      complete.current(response.data.data.message || 'ChatGPT connected.');
    } catch (error) { setMessage(errorMessage(error)); }
    finally { setBusy(false); }
  };

  const cancel = async () => {
    setBusy(true);
    try {
      await axios.post(`/api/v1/model-providers/${flow.providerId}/oauth/cancel`);
      setCallbackUrl('');
      onCancel();
    } catch (error) { setMessage(errorMessage(error)); }
    finally { setBusy(false); }
  };

  return (
    <section aria-label="ChatGPT sign-in" className="space-y-3 rounded-xl border border-cyan-400/30 bg-shogun-card p-5">
      <h2 className="text-sm font-bold text-shogun-text">Connect with ChatGPT</h2>
      <p className="text-xs text-shogun-subdued" role="status">{message}</p>
      {flow.callback_warning && <p className="text-xs text-amber-300">{flow.callback_warning}</p>}
      {!retired && <>
        <a href={flow.authorization_url} target="_blank" rel="noopener noreferrer" className="inline-block text-sm text-cyan-300 underline">Open sign-in</a>
        <p className="text-xs text-shogun-subdued">If the localhost return page cannot open, copy its entire address and paste it here. This link is sensitive; do not share it.</p>
        <label className="block text-xs text-shogun-text">Callback URL
          <input type="password" autoComplete="off" spellCheck={false} value={callbackUrl}
            onChange={event => setCallbackUrl(event.target.value)} disabled={busy} maxLength={16384}
            placeholder="http://localhost:1455/auth/callback?…"
            className="mt-1 block w-full rounded-lg border border-shogun-border bg-shogun-bg p-3 text-sm" />
        </label>
        <button type="button" disabled={busy || !callbackUrl.trim()} onClick={() => void finish()}
          className="rounded-lg border border-cyan-400/30 px-3 py-2 text-xs text-cyan-300 disabled:opacity-50">
          {busy ? 'Working…' : 'Complete secure connection'}
        </button>
      </>}
      <button type="button" disabled={busy} onClick={() => void cancel()}
        className="ml-2 rounded-lg border border-shogun-border px-3 py-2 text-xs text-shogun-text disabled:opacity-50">
        {retired ? 'Close sign-in' : 'Cancel sign-in'}
      </button>
      <p className="text-xs text-shogun-subdued">Cancellation keeps any previously connected account.</p>
    </section>
  );
}
