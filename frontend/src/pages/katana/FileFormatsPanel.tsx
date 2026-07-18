import { useEffect, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, CheckCircle2, FileSearch, Loader2, Search, ShieldCheck } from 'lucide-react';

type Format = {
  format_id: string;
  display_name: string;
  extensions: string[];
  capabilities: string[];
  risk_level: string;
  supports_write: boolean;
  supports_indexing: boolean;
  status: string;
};

export function FileFormatsPanel() {
  const [formats, setFormats] = useState<Format[]>([]);
  const [path, setPath] = useState('');
  const [inspection, setInspection] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    axios.get('/api/v1/files/formats').then(response => setFormats(response.data.data || [])).catch(() => setError('Could not load the adapter registry.'));
  }, []);

  const inspect = async () => {
    if (!path.trim()) return;
    setLoading(true);
    setError('');
    setInspection(null);
    try {
      const response = await axios.post('/api/v1/files/inspect', { path: path.trim(), source: 'katana' });
      setInspection(response.data.data);
    } catch (cause: any) {
      setError(cause?.response?.data?.detail?.message || cause?.response?.data?.detail || 'File inspection failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="rounded-xl border border-cyan-400/20 bg-cyan-500/[0.04] p-5">
        <div className="flex items-start gap-3">
          <ShieldCheck className="h-5 w-5 shrink-0 text-cyan-400" />
          <div>
            <h3 className="text-sm font-bold text-shogun-text">Broader File Format Handling</h3>
            <p className="mt-1 text-xs leading-relaxed text-shogun-subdued">Files are detected, safety-checked, parsed deterministically, normalized, and registered before an agent reasons over them. Previews are bounded and likely secrets are masked.</p>
          </div>
        </div>
      </div>

      <div className="shogun-card space-y-4">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-bold text-shogun-text"><FileSearch className="h-4 w-4 text-shogun-gold" /> Inspect an approved file</h3>
          <p className="mt-1 text-[11px] text-shogun-subdued">Use a file inside the Shogun workspace, uploads, Office, Mado, memory-artifact, or installation workspace boundaries.</p>
        </div>
        <div className="flex gap-2">
          <input value={path} onChange={event => setPath(event.target.value)} onKeyDown={event => event.key === 'Enter' && inspect()} placeholder="C:\\...\\workspace\\orders.csv" className="min-w-0 flex-1 rounded-lg border border-shogun-border bg-shogun-bg px-3 py-2 text-xs text-shogun-text outline-none focus:border-shogun-blue" />
          <button onClick={inspect} disabled={loading || !path.trim()} className="inline-flex items-center gap-2 rounded-lg bg-shogun-blue px-4 py-2 text-xs font-bold text-white disabled:opacity-50">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />} Inspect
          </button>
        </div>
        {error && <div className="flex items-center gap-2 rounded-lg border border-red-400/25 bg-red-500/5 p-3 text-xs text-red-300"><AlertTriangle className="h-4 w-4" />{String(error)}</div>}
        {inspection && (
          <div className="space-y-3 rounded-xl border border-shogun-border bg-shogun-bg/60 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-400" />
              <span className="font-bold text-shogun-text">{inspection.filename}</span>
              <span className="rounded border border-cyan-400/25 bg-cyan-500/5 px-2 py-0.5 text-[10px] font-bold uppercase text-cyan-300">{inspection.format_id}</span>
              <span className="text-[10px] text-shogun-subdued">{Math.round((inspection.detection?.confidence || 0) * 100)}% via {inspection.detection?.method}</span>
            </div>
            <p className="text-xs text-shogun-subdued">{inspection.summary}</p>
            <div className="grid grid-cols-2 gap-3 text-[10px] md:grid-cols-4">
              <div><span className="block text-shogun-subdued">Size</span><span className="text-shogun-text">{Number(inspection.size_bytes).toLocaleString()} bytes</span></div>
              <div><span className="block text-shogun-subdued">Encoding</span><span className="text-shogun-text">{inspection.encoding || 'binary'}</span></div>
              <div><span className="block text-shogun-subdued">File ID</span><span className="break-all text-shogun-text">{inspection.file_id || 'not registered'}</span></div>
              <div><span className="block text-shogun-subdued">SHA-256</span><span className="break-all text-shogun-text">{inspection.hash_sha256?.slice(0, 16)}…</span></div>
            </div>
            <div className="flex flex-wrap gap-1.5">{(inspection.capabilities || []).map((capability: string) => <span key={capability} className="rounded bg-shogun-card px-2 py-1 text-[9px] uppercase text-shogun-subdued">{capability}</span>)}</div>
            {(inspection.warnings || []).map((warning: string) => <div key={warning} className="flex gap-2 text-[10px] text-amber-300"><AlertTriangle className="h-3.5 w-3.5 shrink-0" />{warning}</div>)}
            <details className="text-xs"><summary className="cursor-pointer font-bold text-shogun-blue">Normalized preview and schema</summary><pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-black/30 p-3 text-[10px] text-shogun-subdued">{JSON.stringify({ schema: inspection.schema, profile: inspection.data, preview: inspection.preview }, null, 2)}</pre></details>
          </div>
        )}
      </div>

      <div className="shogun-card overflow-hidden !p-0">
        <div className="border-b border-shogun-border p-5"><h3 className="text-sm font-bold text-shogun-text">Adapter Registry</h3><p className="mt-1 text-[11px] text-shogun-subdued">New proprietary adapters can register here without changing the generic file tool pipeline.</p></div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[10px]">
            <thead className="bg-shogun-bg uppercase tracking-wider text-shogun-subdued"><tr><th className="p-3">Format</th><th className="p-3">Extensions</th><th className="p-3">Read</th><th className="p-3">Write</th><th className="p-3">Query</th><th className="p-3">Index</th><th className="p-3">Risk</th><th className="p-3">Status</th></tr></thead>
            <tbody className="divide-y divide-shogun-border">{formats.map(format => <tr key={format.format_id} className="text-shogun-subdued"><td className="p-3 font-bold text-shogun-text">{format.display_name}</td><td className="p-3">{format.extensions.join(', ') || 'fallback'}</td><td className="p-3 text-green-400">Yes</td><td className="p-3">{format.supports_write ? 'Yes' : '—'}</td><td className="p-3">{format.capabilities.includes('query') ? 'Yes' : '—'}</td><td className="p-3">{format.supports_indexing ? 'Profile' : '—'}</td><td className="p-3 uppercase">{format.risk_level}</td><td className="p-3 uppercase text-cyan-300">{format.status}</td></tr>)}</tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
