import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from '../lib/routerCompat';
import { 
  Mail, RefreshCw, Send, Trash2, Plus, 
  ChevronLeft, ChevronRight, AlertCircle, ShieldAlert, 
  Folder, Inbox, Trash, Archive, X
} from 'lucide-react';
import { cn } from '../lib/utils';

// Types
interface EmailAccount {
  id: string;
  provider: string;
  email_address: string;
  display_name?: string;
  perm_read_mail: boolean;
  perm_send_mail: boolean;
  perm_delete_mail: boolean;
  is_active: boolean;
  calendar_provider: string;
}

interface MessageSummary {
  uid: string;
  from_address: string;
  to_address: string;
  subject: string;
  date: string;
  body_preview: string;
  is_read: boolean;
  has_attachments: boolean;
}

interface FullMessage extends MessageSummary {
  body_html?: string;
  body_text?: string;
  attachments?: Array<{ filename: string; content_type: string; size: number }>;
}

export const MailView = () => {
  const navigate = useNavigate();
  // states
  const [account, setAccount] = useState<EmailAccount | null>(null);
  const [loadingAccount, setLoadingAccount] = useState(true);
  const [folders, setFolders] = useState<string[]>([]);
  const [activeFolder, setActiveFolder] = useState('INBOX');
  const [messages, setMessages] = useState<MessageSummary[]>([]);
  const [totalMessages, setTotalMessages] = useState(0);
  const [page, setPage] = useState(1);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [selectedMessage, setSelectedMessage] = useState<FullMessage | null>(null);
  const [loadingFullMessage, setLoadingFullMessage] = useState(false);
  
  // Compose modal
  const [showCompose, setShowCompose] = useState(false);
  const [composeTo, setComposeTo] = useState('');
  const [composeCc, setComposeCc] = useState('');
  const [composeBcc, setComposeBcc] = useState('');
  const [composeSubject, setComposeSubject] = useState('');
  const [composeBody, setComposeBody] = useState('');
  const [sendingEmail, setSendingEmail] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // fetch account details
  const fetchAccount = async () => {
    try {
      const res = await axios.get('/api/v1/channels/email/account');
      setAccount(res.data.data);
    } catch {
      setAccount(null);
    } finally {
      setLoadingAccount(false);
    }
  };

  useEffect(() => {
    fetchAccount();
  }, []);

  // Fetch folders and messages when account changes
  useEffect(() => {
    if (account?.is_active && account.perm_read_mail) {
      fetchFolders();
    }
  }, [account]);

  // Fetch messages when folder or page changes
  useEffect(() => {
    if (account?.is_active && account.perm_read_mail) {
      fetchMessages();
    }
  }, [account, activeFolder, page]);

  const fetchFolders = async () => {
    try {
      const res = await axios.get('/api/v1/channels/email/account/folders');
      setFolders(res.data.data || []);
    } catch (e) {
      console.error("Failed to fetch folders", e);
    }
  };

  const fetchMessages = async () => {
    setLoadingMessages(true);
    try {
      const res = await axios.get(`/api/v1/channels/email/account/messages`, {
        params: { folder: activeFolder, page, per_page: 15 }
      });
      setMessages(res.data.data.messages || []);
      setTotalMessages(res.data.data.total || 0);
    } catch (e) {
      console.error("Failed to fetch messages", e);
    } finally {
      setLoadingMessages(false);
    }
  };

  const loadFullMessage = async (uid: string) => {
    setLoadingFullMessage(true);
    try {
      const res = await axios.get(`/api/v1/channels/email/account/messages/${uid}`, {
        params: { folder: activeFolder }
      });
      setSelectedMessage(res.data.data);
      // Mark read locally
      setMessages(prev => prev.map(m => m.uid === uid ? { ...m, is_read: true } : m));
    } catch (e) {
      console.error("Failed to load message body", e);
    } finally {
      setLoadingFullMessage(false);
    }
  };

  const handleMarkUnread = async (uid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await axios.post(`/api/v1/channels/email/account/messages/${uid}/unread`, null, {
        params: { folder: activeFolder }
      });
      setMessages(prev => prev.map(m => m.uid === uid ? { ...m, is_read: false } : m));
      if (selectedMessage?.uid === uid) {
        setSelectedMessage(prev => prev ? { ...prev, is_read: false } : null);
      }
    } catch (e) {
      console.error("Failed to mark unread", e);
    }
  };

  const handleDelete = async (uid: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (!account?.perm_delete_mail) return;
    try {
      await axios.delete(`/api/v1/channels/email/account/messages/${uid}`, {
        params: { folder: activeFolder }
      });
      if (selectedMessage?.uid === uid) {
        setSelectedMessage(null);
      }
      fetchMessages();
    } catch (e) {
      console.error("Failed to delete message", e);
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!account?.perm_send_mail) return;
    setSendingEmail(true);
    setErrorMsg('');
    setSuccessMsg('');
    try {
      await axios.post('/api/v1/channels/email/account/send', {
        to_address: composeTo,
        cc_address: composeCc,
        bcc_address: composeBcc,
        subject: composeSubject,
        body: composeBody
      });
      setSuccessMsg('Email sent successfully!');
      setComposeTo('');
      setComposeCc('');
      setComposeBcc('');
      setComposeSubject('');
      setComposeBody('');
      await fetchFolders();
      await fetchMessages();
      setTimeout(() => {
        setShowCompose(false);
        setSuccessMsg('');
      }, 1500);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to send email.');
    } finally {
      setSendingEmail(false);
    }
  };

  const getFolderIcon = (name: string) => {
    const lname = name.toLowerCase();
    if (lname === 'inbox') return <Inbox className="w-4 h-4" />;
    if (lname.includes('trash') || lname.includes('bin')) return <Trash className="w-4 h-4" />;
    if (lname.includes('archive')) return <Archive className="w-4 h-4" />;
    if (lname.includes('sent')) return <Send className="w-4 h-4" />;
    return <Folder className="w-4 h-4" />;
  };

  const totalPages = Math.ceil(totalMessages / 15);

  if (loadingAccount) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-shogun-subdued space-y-4">
        <RefreshCw className="w-8 h-8 animate-spin text-shogun-blue" />
        <p className="text-xs uppercase tracking-widest font-bold">Synchronizing Mail Client…</p>
      </div>
    );
  }

  if (!account || !account.is_active) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-shogun-subdued text-center p-8">
        <div className="w-16 h-16 rounded-full bg-shogun-blue/10 flex items-center justify-center text-shogun-blue border border-shogun-blue/30 mb-4 animate-pulse">
          <Mail className="w-8 h-8" />
        </div>
        <h4 className="text-lg font-bold text-shogun-text mb-2">No Mail Account Connected</h4>
        <p className="max-w-md text-xs text-shogun-subdued leading-relaxed mb-6">
          To receive, compose, and organize mail, configure your provider in the Katana settings.
        </p>
        <button
          onClick={() => {
            navigate('/katana');
          }}
          className="px-5 py-2.5 bg-shogun-blue hover:bg-shogun-blue/90 text-white text-xs font-bold rounded-lg uppercase tracking-wider transition-all"
        >
          Go to Katana Settings
        </button>
      </div>
    );
  }

  if (!account.perm_read_mail) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-shogun-subdued text-center p-8">
        <div className="w-16 h-16 rounded-full bg-red-400/10 flex items-center justify-center text-red-400 border border-red-400/30 mb-4">
          <ShieldAlert className="w-8 h-8" />
        </div>
        <h4 className="text-lg font-bold text-shogun-text mb-2">Read Permission Denied</h4>
        <p className="max-w-md text-xs text-shogun-subdued leading-relaxed">
          The "Read Mail" permission is disabled for this account in Katana settings. Toggle this permission ON to view your inbox.
        </p>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-270px)] flex flex-col min-h-0 bg-[#050508]/30 rounded-2xl border border-shogun-border/40 overflow-hidden backdrop-blur-md">
      {/* Top action bar */}
      <div className="flex justify-between items-center px-6 py-4 bg-[#0a0a0f]/60 border-b border-shogun-border/40 shrink-0">
        <div className="flex items-center gap-3">
          <div className="px-2.5 py-1 rounded bg-shogun-blue/10 border border-shogun-blue/30 text-shogun-blue text-[10px] font-bold uppercase">
            {account.provider}
          </div>
          <span className="text-xs text-shogun-subdued font-medium">{account.email_address}</span>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => { fetchFolders(); fetchMessages(); }}
            className="p-2 border border-shogun-border bg-shogun-card hover:bg-shogun-card/80 text-shogun-subdued hover:text-shogun-text rounded-lg transition-all"
            title="Refresh mail"
          >
            <RefreshCw className={cn("w-4 h-4", loadingMessages && "animate-spin")} />
          </button>
          
          {account.perm_send_mail && (
            <button
              onClick={() => setShowCompose(true)}
              className="flex items-center gap-1.5 px-4 py-2 bg-shogun-blue hover:bg-shogun-blue/90 text-white font-bold rounded-lg text-xs uppercase tracking-wider transition-all"
            >
              <Plus className="w-4 h-4" /> Compose
            </button>
          )}
        </div>
      </div>

      {/* Main split pane */}
      <div className="flex-1 flex min-h-0 divide-x divide-shogun-border/30">
        {/* Left Column: Folders */}
        <div className="w-48 bg-[#0a0a0f]/30 p-4 space-y-1.5 overflow-y-auto shrink-0">
          <span className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest block px-2 mb-2">Folders</span>
          {folders.length === 0 ? (
            <div className="text-[11px] text-shogun-subdued italic px-2">No folders loaded.</div>
          ) : (
            folders.map(f => (
              <button
                key={f}
                onClick={() => { setActiveFolder(f); setPage(1); setSelectedMessage(null); }}
                className={cn(
                  "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all text-left",
                  activeFolder === f 
                    ? "bg-shogun-blue/10 text-shogun-blue border border-shogun-blue/20" 
                    : "text-shogun-subdued hover:text-shogun-text hover:bg-shogun-card/40"
                )}
              >
                {getFolderIcon(f)}
                <span className="truncate">{f}</span>
              </button>
            ))
          )}
        </div>

        {/* Center Column: Message List */}
        <div className="flex-1 flex flex-col min-w-0 bg-[#07070a]/40 divide-y divide-shogun-border/30">
          <div className="flex-1 overflow-y-auto min-h-0">
            {loadingMessages ? (
              <div className="h-full flex flex-col items-center justify-center text-shogun-subdued space-y-3 opacity-55">
                <RefreshCw className="w-6 h-6 animate-spin text-shogun-blue" />
                <p className="text-[10px] uppercase tracking-wider">Fetching messages…</p>
              </div>
            ) : messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-shogun-subdued space-y-2 opacity-50 p-6 text-center">
                <Mail className="w-10 h-10" />
                <p className="text-xs italic">Folder {activeFolder} is empty.</p>
              </div>
            ) : (
              <div className="divide-y divide-shogun-border/25">
                {messages.map(msg => (
                  <div
                    key={msg.uid}
                    onClick={() => loadFullMessage(msg.uid)}
                    className={cn(
                      "p-4 cursor-pointer hover:bg-shogun-card/30 transition-all border-l-2 flex flex-col gap-1.5 relative",
                      selectedMessage?.uid === msg.uid 
                        ? "bg-shogun-blue/5 border-l-shogun-blue" 
                        : msg.is_read 
                          ? "border-l-transparent" 
                          : "border-l-shogun-gold bg-shogun-gold/[0.02]"
                    )}
                  >
                    <div className="flex justify-between items-start gap-4">
                      <span className={cn(
                        "text-xs truncate max-w-[70%]",
                        msg.is_read ? "text-shogun-text/80 font-medium" : "text-shogun-gold font-bold"
                      )}>
                        {msg.from_address}
                      </span>
                      <span className="text-[10px] text-shogun-subdued shrink-0 font-mono">
                        {msg.date.split(',')[1]?.trim()?.slice(0, 11) || msg.date}
                      </span>
                    </div>

                    <p className={cn(
                      "text-xs truncate",
                      msg.is_read ? "text-shogun-text/90" : "text-shogun-text font-bold"
                    )}>
                      {msg.subject || "(No Subject)"}
                    </p>

                    <p className="text-[10px] text-shogun-subdued truncate max-w-full leading-normal">
                      {msg.body_preview || "No preview available"}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Pagination bar */}
          {totalPages > 1 && (
            <div className="flex justify-between items-center px-4 py-3 bg-[#0a0a0f]/60 shrink-0 border-t border-shogun-border/30">
              <span className="text-[10px] text-shogun-subdued font-bold">
                Page {page} of {totalPages} ({totalMessages} messages)
              </span>
              <div className="flex gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                  className="p-1 border border-shogun-border bg-shogun-card hover:bg-shogun-card/80 rounded disabled:opacity-40 disabled:hover:bg-shogun-card transition-all"
                >
                  <ChevronLeft className="w-4 h-4 text-shogun-text" />
                </button>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                  className="p-1 border border-shogun-border bg-shogun-card hover:bg-shogun-card/80 rounded disabled:opacity-40 disabled:hover:bg-shogun-card transition-all"
                >
                  <ChevronRight className="w-4 h-4 text-shogun-text" />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Message Reader */}
        <div className="w-1/2 flex flex-col min-w-0 bg-[#050508]/40 overflow-hidden">
          {loadingFullMessage ? (
            <div className="flex-1 flex flex-col items-center justify-center text-shogun-subdued space-y-4">
              <RefreshCw className="w-7 h-7 animate-spin text-shogun-gold" />
              <p className="text-[10px] uppercase tracking-wider font-bold">Loading full message payload…</p>
            </div>
          ) : !selectedMessage ? (
            <div className="flex-1 flex flex-col items-center justify-center text-shogun-subdued space-y-2 opacity-50 p-6 text-center">
              <Mail className="w-12 h-12" />
              <p className="text-xs italic">Select an email to view details.</p>
            </div>
          ) : (
            <div className="flex-1 flex flex-col min-h-0">
              {/* Reader Header */}
              <div className="p-5 border-b border-shogun-border/30 bg-[#0a0a0f]/40 space-y-3 shrink-0">
                <div className="flex justify-between items-start gap-4">
                  <h3 className="text-sm font-bold text-shogun-text leading-snug">
                    {selectedMessage.subject || "(No Subject)"}
                  </h3>
                  <div className="flex gap-1.5 shrink-0">
                    <button
                      onClick={(e) => handleMarkUnread(selectedMessage.uid, e)}
                      className="px-2 py-1 text-[10px] font-bold border border-shogun-border text-shogun-subdued hover:text-shogun-text rounded hover:bg-shogun-card/40 transition-all"
                    >
                      Mark Unread
                    </button>
                    {account.perm_delete_mail && (
                      <button
                        onClick={() => handleDelete(selectedMessage.uid)}
                        className="p-1 border border-red-500/20 text-red-400/80 hover:text-red-400 hover:bg-red-500/10 rounded transition-all"
                        title="Delete Email"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                <div className="space-y-1 text-xs">
                  <div className="flex gap-2">
                    <span className="text-shogun-subdued font-semibold w-10 shrink-0">From:</span>
                    <span className="text-shogun-text font-mono truncate">{selectedMessage.from_address}</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-shogun-subdued font-semibold w-10 shrink-0">To:</span>
                    <span className="text-shogun-text font-mono truncate">{selectedMessage.to_address}</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-shogun-subdued font-semibold w-10 shrink-0">Date:</span>
                    <span className="text-shogun-subdued font-mono truncate">{selectedMessage.date}</span>
                  </div>
                </div>
              </div>

              {/* Reader Body */}
              <div className="flex-1 p-5 overflow-y-auto min-h-0 bg-[#030305]/80 space-y-4">
                {selectedMessage.body_html ? (
                  <div className="w-full h-full min-h-[300px] border border-shogun-border/20 rounded-xl overflow-hidden bg-white/5">
                    <iframe
                      title="email-body"
                      sandbox="allow-popups allow-popups-to-escape-sandbox"
                      srcDoc={`
                        <html>
                          <head>
                            <style>
                              body {
                                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                                font-size: 14px;
                                line-height: 1.6;
                                color: #d1d5db;
                                background-color: #0d0d14;
                                padding: 16px;
                                margin: 0;
                                word-break: break-word;
                              }
                              a {
                                color: #3b82f6;
                                text-decoration: underline;
                              }
                              img {
                                max-width: 100%;
                                height: auto;
                              }
                              pre {
                                background-color: #161622;
                                border: 1px solid #232334;
                                padding: 12px;
                                border-radius: 8px;
                                overflow-x: auto;
                                color: #f59e0b;
                                font-family: monospace;
                              }
                            </style>
                          </head>
                          <body>
                            ${selectedMessage.body_html}
                          </body>
                        </html>
                      `}
                      className="w-full h-full border-none"
                    />
                  </div>
                ) : (
                  <div className="text-xs text-shogun-text font-mono whitespace-pre-wrap leading-relaxed bg-[#0a0a0f]/80 p-4 border border-shogun-border/20 rounded-xl">
                    {selectedMessage.body_text || "(Empty body)"}
                  </div>
                )}

                {/* Attachments Section */}
                {selectedMessage.attachments && selectedMessage.attachments.length > 0 && (
                  <div className="pt-4 border-t border-shogun-border/30 space-y-2">
                    <span className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest block">Attachments</span>
                    <div className="grid grid-cols-1 gap-2">
                      {selectedMessage.attachments.map(att => (
                        <div key={att.filename} className="p-3 rounded-lg border border-shogun-border/20 bg-shogun-card flex items-center justify-between">
                          <div className="min-w-0">
                            <p className="text-xs text-shogun-text truncate font-medium">{att.filename}</p>
                            <p className="text-[10px] text-shogun-subdued mt-0.5">{att.content_type} · {(att.size / 1024).toFixed(1)} KB</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Compose Modal ───────────────────────────────────────── */}
      {showCompose && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-md"
            onClick={() => { if (!sendingEmail) setShowCompose(false); }}
          />

          <div className="relative w-full max-w-lg bg-[#09090e] border border-shogun-border rounded-2xl flex flex-col shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center px-5 py-3 border-b border-shogun-border/30 bg-[#0a0a0f]/40">
              <h3 className="text-sm font-bold text-shogun-text uppercase tracking-widest flex items-center gap-2">
                <Send className="w-4 h-4 text-shogun-blue" />
                Compose Directive
              </h3>
              <button
                disabled={sendingEmail}
                onClick={() => setShowCompose(false)}
                className="p-1 text-shogun-subdued hover:text-shogun-text transition-colors disabled:opacity-40"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSend} className="p-4 flex-1 flex flex-col gap-3 overflow-y-auto max-h-[55vh]">
              {errorMsg && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded-lg text-xs font-semibold flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}
              {successMsg && (
                <div className="p-3 bg-green-500/10 border border-green-500/20 text-green-500 rounded-lg text-xs font-semibold flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{successMsg}</span>
                </div>
              )}

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">To *</label>
                <input
                  type="email"
                  required
                  placeholder="recipient@domain.com"
                  value={composeTo}
                  onChange={e => setComposeTo(e.target.value)}
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Cc</label>
                  <input
                    type="text"
                    placeholder="cc@domain.com, cc2@domain.com"
                    value={composeCc}
                    onChange={e => setComposeCc(e.target.value)}
                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Bcc</label>
                  <input
                    type="text"
                    placeholder="bcc@domain.com"
                    value={composeBcc}
                    onChange={e => setComposeBcc(e.target.value)}
                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Subject *</label>
                <input
                  type="text"
                  required
                  placeholder="Enter subject title"
                  value={composeSubject}
                  onChange={e => setComposeSubject(e.target.value)}
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                />
              </div>

              <div className="space-y-1.5 flex-1 flex flex-col">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Body *</label>
                <textarea
                  required
                  rows={4}
                  placeholder="Write message contents..."
                  value={composeBody}
                  onChange={e => setComposeBody(e.target.value)}
                  className="w-full flex-1 min-h-[80px] bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono resize-y"
                />
              </div>

              <button
                type="submit"
                disabled={sendingEmail || !composeTo || !composeSubject || !composeBody}
                className="w-full flex items-center justify-center gap-2 py-3 bg-shogun-blue hover:bg-shogun-blue/90 disabled:opacity-40 text-white font-bold rounded-lg text-sm uppercase tracking-wider transition-all mt-2"
              >
                {sendingEmail ? (
                  <><RefreshCw className="w-4 h-4 animate-spin" /> Transmitting Directive…</>
                ) : (
                  <><Send className="w-4 h-4" /> Transmit Email</>
                )}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
