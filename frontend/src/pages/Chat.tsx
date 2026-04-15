import { useState, useEffect, useRef } from 'react';
import { Send, Terminal, Bot, User, Trash2, Loader2 } from 'lucide-react';
import axios from 'axios';
import { cn } from '../lib/utils';

interface Message {
  role: 'user' | 'shogun';
  content: string;
  timestamp: string;
}

export const Chat = () => {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'shogun', content: 'Systems stabilized. I am ready for directives, Shogun.', timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
  ]);
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

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
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) 
    };
    
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsThinking(true);

    try {
      const response = await axios.post('/api/v1/agents/shogun/chat', { message: input });
      const data = response.data.data;
      
      const shogunMsg: Message = { 
        role: 'shogun', 
        content: data.response, 
        timestamp: data.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) 
      };
      setMessages(prev => [...prev, shogunMsg]);
    } catch (err) {
      console.error("Failed to send directive:", err);
      const errorMsg: Message = {
        role: 'shogun',
        content: "Error: Terminal bridge interrupted. Please verify backend connectivity.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            Comms <span className="text-xs font-normal text-shogun-subdued bg-shogun-card px-2 py-1 rounded border border-shogun-border tracking-[0.2em] uppercase">Interface</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">Direct encrypted link to primary Shogun agent.</p>
        </div>
        <button 
          onClick={() => setMessages([])}
          className="p-2 text-shogun-subdued hover:text-red-500 hover:bg-red-500/10 rounded-lg transition-all"
          title="Clear Terminal"
        >
          <Trash2 className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 shogun-card overflow-hidden flex flex-col p-0">
        <div 
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-hide scroll-smooth"
        >
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-shogun-subdued space-y-3 opacity-50">
              <Terminal className="w-12 h-12" />
              <p className="text-sm italic tracking-wide">Terminal empty. Waiting for input...</p>
            </div>
          )}
          
          {messages.map((msg, i) => (
            <div key={i} className={cn(
              "flex gap-4 animate-in fade-in slide-in-from-bottom-2 duration-300",
              msg.role === 'user' ? "flex-row-reverse" : "flex-row"
            )}>
              <div className={cn(
                "w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border",
                msg.role === 'user' ? "bg-shogun-blue/10 border-shogun-blue/30 text-shogun-blue" : "bg-shogun-gold/10 border-shogun-gold/30 text-shogun-gold"
              )}>
                {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>
              
              <div className={cn(
                "max-w-[70%] space-y-1 flex flex-col",
                msg.role === 'user' ? "items-end" : "items-start"
              )}>
                <div className={cn(
                  "p-4 rounded-2xl text-sm leading-relaxed",
                  msg.role === 'user' 
                    ? "bg-shogun-card border border-shogun-border text-shogun-text rounded-tr-none" 
                    : "bg-[#050508] border border-shogun-border text-shogun-gold rounded-tl-none font-mono"
                )}>
                  {msg.content}
                </div>
                <span className="text-[10px] text-shogun-subdued px-1">{msg.timestamp}</span>
              </div>
            </div>
          ))}

          {isThinking && (
            <div className="flex gap-4 animate-in fade-in duration-300">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border bg-shogun-gold/10 border-shogun-gold/30 text-shogun-gold">
                <Bot className="w-4 h-4" />
              </div>
              <div className="flex items-center gap-2 text-shogun-subdued text-xs italic font-mono p-4">
                <Loader2 className="w-3 h-3 animate-spin" />
                Shogun is processing directive...
              </div>
            </div>
          )}
        </div>

        <div className="p-4 bg-[#050508]/50 border-t border-shogun-border">
          <div className="relative flex items-center">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              disabled={isThinking}
              placeholder={isThinking ? "Awaiting agent response..." : "Enter directive..."}
              className="w-full bg-shogun-card border border-shogun-border rounded-xl py-4 pl-6 pr-14 text-shogun-text placeholder:text-shogun-subdued focus:outline-none focus:border-shogun-blue focus:ring-1 focus:ring-shogun-blue/20 transition-all font-mono text-sm disabled:opacity-50"
            />
            <button 
              onClick={handleSend}
              disabled={isThinking || !input.trim()}
              className="absolute right-2 p-2 bg-shogun-blue text-white rounded-lg hover:bg-shogun-blue/80 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isThinking ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
            </button>
          </div>
          <div className="flex justify-between mt-3 px-2">
             <div className="flex gap-4">
                <span className="text-[10px] text-shogun-subdued flex items-center gap-1"><Terminal className="w-3 h-3" /> UTF-8</span>
                <span className="text-[10px] text-shogun-subdued flex items-center gap-1 underline cursor-pointer hover:text-shogun-blue">View History</span>
             </div>
             <span className="text-[10px] text-shogun-subdued italic">Shift + Enter for new line</span>
          </div>
        </div>
      </div>
    </div>
  );
};

