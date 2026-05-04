import { useState, useEffect, useRef } from 'react';
import { Send, Terminal, Bot, User, Trash2, History, X, ChevronDown, ChevronRight, Globe } from 'lucide-react';
import { cn } from '../lib/utils';
import { useTranslation } from '../i18n';

interface Message {
  role: 'user' | 'shogun';
  content: string;
  timestamp: string;
  model?: string;
  provider?: string;
  search?: boolean;
}

interface Session {
  id: string;
  startedAt: string;
  messages: Message[];
}

const STORAGE_KEY = 'shogun_comms_current';
const HISTORY_KEY = 'shogun_comms_history';
const MAX_HISTORY_SESSIONS = 50;

const WELCOME_KEY = 'chat.welcome_message';

function loadCurrent(t: any): Message[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [{
      role: 'shogun',
      content: t(WELCOME_KEY),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }];
  } catch {
    return [{
      role: 'shogun',
      content: t(WELCOME_KEY),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }];
  }
}

function saveCurrent(msgs: Message[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(msgs));
}

function loadHistory(): Session[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function archiveSession(msgs: Message[], t: any) {
  // Only archive if there was actual conversation (more than just the welcome)
  const welcomeText = t(WELCOME_KEY);
  const real = msgs.filter(m => !(m.role === 'shogun' && m.content === welcomeText));
  if (real.length === 0) return;

  const history = loadHistory();
  const session: Session = {
    id: Date.now().toString(),
    startedAt: msgs[0]?.timestamp || new Date().toLocaleTimeString(),
    messages: msgs,
  };
  const updated = [session, ...history].slice(0, MAX_HISTORY_SESSIONS);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(updated));
}

export const Chat = () => {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<Message[]>(() => loadCurrent(t));
  const operatorName = localStorage.getItem('shogun_operator_name') || 'Daimyo';
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<Session[]>(loadHistory);
  const [expandedSession, setExpandedSession] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Persist messages to localStorage on every change
  useEffect(() => {
    saveCurrent(messages);
  }, [messages]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isThinking]);

  const handleSend = async () => {
    if (!input.trim() || isThinking) return;

    const userMsg: Message = {
      role: 'user',
      content: input,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput('');
    setIsThinking(true);

    const hist = updatedMessages
      .filter(m => m.role === 'user' || m.role === 'shogun')
      .slice(-20)
      .map(m => ({ role: m.role === 'shogun' ? 'assistant' : 'user', content: m.content }));

    // Placeholder message that we'll fill in as tokens arrive
    const placeholder: Message = {
      role: 'shogun',
      content: '',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages(prev => [...prev, placeholder]);
    // Keep isThinking=true until first token so input stays locked

    try {
      const resp = await fetch('/api/v1/agents/shogun/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input, history: hist.slice(0, -1) }),
      });

      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let assembled = '';
      let meta: { model?: string; provider?: string; timestamp?: string; search?: boolean } = {};

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (raw === '[DONE]') break;

          try {
            const evt = JSON.parse(raw);

            if (evt.type === 'meta') {
              meta = { 
                model: evt.model, 
                provider: evt.provider, 
                timestamp: evt.timestamp,
                search: evt.search 
              };
              setIsThinking(false); // first event received — hide the typing indication
              setMessages(prev => {
                const copy = [...prev];
                copy[copy.length - 1] = { ...copy[copy.length - 1], ...meta };
                return copy;
              });
            } else if (evt.type === 'token') {
              setIsThinking(false); // first token — stop animation
              assembled += evt.content;
              const snap = assembled;
              setMessages(prev => {
                const copy = [...prev];
                copy[copy.length - 1] = { ...copy[copy.length - 1], content: snap };
                return copy;
              });
            } else if (evt.type === 'error') {
              setMessages(prev => {
                const copy = [...prev];
                copy[copy.length - 1] = { ...copy[copy.length - 1], content: evt.content };
                return copy;
              });
            }
          } catch { /* malformed event */ }
        }
      }
    } catch (err) {
      console.error('Streaming failed:', err);
      setMessages(prev => {
        const copy = [...prev];
        copy[copy.length - 1] = {
          ...copy[copy.length - 1],
          content: '⚠️ ' + t('chat.bridge_interrupted', 'Neural bridge interrupted. Check logs.'),
        };
        return copy;
      });
    }
  };

  const handleClear = () => {
    archiveSession(messages, t);
    const fresh: Message[] = [{ 
      role: 'shogun',
      content: t(WELCOME_KEY),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) 
    }];
    setMessages(fresh);
    setHistory(loadHistory());
  };

  const openHistory = () => {
    setHistory(loadHistory());
    setShowHistory(true);
  };

  const restoreSession = (session: Session) => {
    // Archive current first
    archiveSession(messages, t);
    setMessages(session.messages);
    setShowHistory(false);
  };

  return (
    <div className="flex flex-col w-full min-w-0 h-[calc(100vh-140px)] space-y-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            {t('chat.title', 'Comms')}{' '}
            <span className="text-xs font-normal text-shogun-subdued bg-shogun-card px-2 py-1 rounded border border-shogun-border tracking-[0.2em] uppercase">
              {t('chat.badge', 'Command Console')}
            </span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">{t('chat.subtitle', 'Chat Console — Directly orchestrate the Shogun via terminal interface.')}</p>
        </div>
        <button
          onClick={handleClear}
          className="p-2 text-shogun-subdued hover:text-red-500 hover:bg-red-500/10 rounded-lg transition-all"
          title={t('chat.clear_tooltip', 'Clear current session')}
        >
          <Trash2 className="w-5 h-5" />
        </button>
      </div>

      {/* Chat area */}
      <div className="flex-1 w-full shogun-card overflow-hidden flex flex-col p-0">
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-hide scroll-smooth"
        >
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-shogun-subdued space-y-3 opacity-50">
              <Terminal className="w-12 h-12" />
              <p className="text-sm italic tracking-wide">{t('chat.terminal_empty', 'Terminal empty. Awaiting mission parameters.')}</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={cn(
                'flex gap-4 animate-in fade-in slide-in-from-bottom-2 duration-300',
                msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'
              )}
            >
              <div
                className={cn(
                  'w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border',
                  msg.role === 'user'
                    ? 'bg-shogun-blue/10 border-shogun-blue/30 text-shogun-blue'
                    : 'bg-shogun-gold/10 border-shogun-gold/30 text-shogun-gold'
                )}
              >
                {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div
                className={cn(
                  'max-w-[70%] space-y-1 flex flex-col',
                  msg.role === 'user' ? 'items-end' : 'items-start'
                )}
              >
                <div
                  className={cn(
                    'p-4 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap',
                    msg.role === 'user'
                      ? 'bg-shogun-card border border-shogun-border text-shogun-text rounded-tr-none'
                      : 'bg-[#050508] border border-shogun-border text-shogun-gold rounded-tl-none font-mono'
                  )}
                >
                  {msg.role === 'shogun' && msg.content === '' ? (
                    /* Typing animation — shown while waiting for first token */
                    <div className="flex items-center gap-1.5 py-1">
                      <span className="w-2 h-2 rounded-full bg-shogun-gold/70 animate-bounce [animation-delay:0ms]" />
                      <span className="w-2 h-2 rounded-full bg-shogun-gold/70 animate-bounce [animation-delay:150ms]" />
                      <span className="w-2 h-2 rounded-full bg-shogun-gold/70 animate-bounce [animation-delay:300ms]" />
                    </div>
                  ) : msg.content}
                </div>
                <div className="flex items-center gap-2 px-1 mt-1">
                  <span className="text-[10px] text-shogun-subdued font-bold tracking-wider">{msg.role === 'user' ? operatorName : t('chat.agent_label', 'SHOGUN')}</span>
                  <span className="text-[10px] text-shogun-subdued opacity-50">{msg.timestamp}</span>
                  {msg.role === 'shogun' && (msg.model || msg.search) && (
                    <div className={cn(
                      "flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider",
                      msg.search 
                        ? "bg-shogun-blue/10 border border-shogun-blue/30 text-shogun-blue"
                        : "bg-shogun-card border border-shogun-border text-shogun-subdued"
                    )}>
                      {msg.search ? <Globe className="w-2.5 h-2.5" /> : <Bot className="w-2.5 h-2.5" />}
                      {msg.search ? t('chat.web_search', 'Web Search') : msg.model}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Input bar */}
        <div className="p-4 bg-[#050508]/50 border-t border-shogun-border">
          <div className="relative flex items-center">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
              disabled={isThinking}
              placeholder={isThinking ? t('chat.placeholder_thinking', 'Shogun is thinking...') : t('chat.placeholder', 'Enter directive for the Shogun...')}
              className="w-full bg-shogun-card border border-shogun-border rounded-xl py-4 pl-6 pr-14 text-shogun-text placeholder:text-shogun-subdued focus:outline-none focus:border-shogun-blue focus:ring-1 focus:ring-shogun-blue/20 transition-all font-mono text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            />
            <button
              onClick={handleSend}
              disabled={isThinking || !input.trim()}
              className="absolute right-2 p-2 bg-shogun-blue text-white rounded-lg hover:bg-shogun-blue/80 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
          <div className="flex justify-between mt-3 px-2">
            <div className="flex gap-4">
              <span className="text-[10px] text-shogun-subdued flex items-center gap-1">
                <Terminal className="w-3 h-3" /> UTF-8
              </span>
              <button
                onClick={openHistory}
                className="text-[10px] text-shogun-subdued flex items-center gap-1 underline cursor-pointer hover:text-shogun-blue transition-colors"
              >
                <History className="w-3 h-3" />
                {t('chat.view_history', 'View History')} ({history.length} {t('chat.sessions', 'sessions')})
              </button>
            </div>
            <span className="text-[10px] text-shogun-subdued italic">{t('chat.enter_to_send', 'Press Enter to send')}</span>
          </div>
        </div>
      </div>

      {/* ── History Drawer ─────────────────────────────────────── */}
      {showHistory && (
        <div className="fixed inset-0 z-50 flex">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setShowHistory(false)}
          />

          {/* Panel */}
          <div className="absolute right-0 top-0 h-full w-full max-w-xl bg-shogun-bg border-l border-shogun-border flex flex-col shadow-2xl">
            {/* Panel header */}
            <div className="flex items-center justify-between p-5 border-b border-shogun-border shrink-0">
              <div>
                <h3 className="text-lg font-bold text-shogun-text flex items-center gap-2">
                  <History className="w-5 h-5 text-shogun-gold" />
                  {t('chat.comms_history', 'Comms History')}
                </h3>
                <p className="text-[11px] text-shogun-subdued mt-0.5">
                  {history.length} {t('chat.archived_sessions', 'archived sessions')}
                </p>
              </div>
              <button
                onClick={() => setShowHistory(false)}
                className="p-2 text-shogun-subdued hover:text-shogun-text hover:bg-shogun-card rounded-lg transition-all"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Sessions list */}
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {history.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-shogun-subdued space-y-3 opacity-50">
                  <History className="w-10 h-10" />
                  <p className="text-sm italic">{t('chat.no_history', 'No archived sessions found.')}</p>
                </div>
              ) : (
                history.map(session => {
                  const isExpanded = expandedSession === session.id;
                  const preview = session.messages.find(m => m.role === 'user')?.content || '(empty)';
                  const msgCount = session.messages.filter(m => m.role === 'user').length;
                  return (
                    <div key={session.id} className="border border-shogun-border rounded-xl overflow-hidden">
                      {/* Session row */}
                      <div
                        className="flex items-center gap-3 p-3 cursor-pointer hover:bg-shogun-card/50 transition-colors"
                        onClick={() => setExpandedSession(isExpanded ? null : session.id)}
                      >
                        {isExpanded
                          ? <ChevronDown className="w-4 h-4 text-shogun-subdued shrink-0" />
                          : <ChevronRight className="w-4 h-4 text-shogun-subdued shrink-0" />
                        }
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-mono text-shogun-text truncate">{preview}</p>
                          <p className="text-[10px] text-shogun-subdued mt-0.5">
                            {session.startedAt} · {msgCount} {t('chat.messages', 'messages')}
                          </p>
                        </div>
                        <button
                          onClick={e => { e.stopPropagation(); restoreSession(session); }}
                          className="text-[10px] text-shogun-blue hover:text-shogun-gold font-bold uppercase tracking-wider shrink-0 px-2 py-1 border border-shogun-blue/30 rounded-lg transition-colors"
                        >
                          {t('chat.restore', 'RESTORE')}
                        </button>
                      </div>

                      {/* Expanded messages */}
                      {isExpanded && (
                        <div className="border-t border-shogun-border bg-[#050508] p-3 space-y-2 max-h-64 overflow-y-auto">
                          {session.messages.map((m, i) => (
                            <div key={i} className={cn('text-xs', m.role === 'user' ? 'text-right' : 'text-left')}>
                              <span className={cn(
                                'inline-block px-3 py-1.5 rounded-lg max-w-[85%] text-left',
                                m.role === 'user'
                                  ? 'bg-shogun-blue/10 text-shogun-text border border-shogun-blue/20'
                                  : 'bg-shogun-gold/5 text-shogun-gold border border-shogun-gold/10 font-mono'
                              )}>
                                {m.content.length > 120 ? m.content.slice(0, 120) + '…' : m.content}
                              </span>
                              <div className="text-[9px] text-shogun-subdued mt-0.5 px-1">{m.timestamp}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>

            {/* Clear all history */}
            {history.length > 0 && (
              <div className="p-4 border-t border-shogun-border shrink-0">
                <button
                  onClick={() => {
                    localStorage.removeItem(HISTORY_KEY);
                    setHistory([]);
                  }}
                  className="w-full text-xs text-red-400/60 hover:text-red-400 transition-colors py-2 border border-red-400/10 hover:border-red-400/30 rounded-lg"
                >
                  {t('chat.clear_all_history', 'CLEAR ALL HISTORY')}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
