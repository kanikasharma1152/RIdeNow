import React, { useState, useEffect, useRef } from 'react';
import { getDriverBriefing, chatDriverCopilot } from '../../services/copilotService';
import { 
  Bot, 
  User,
  Send, 
  Sparkles, 
  MapPin, 
  Compass, 
  Lightbulb, 
  Flame,
  ArrowRight,
  RotateCcw,
  Trash2
} from 'lucide-react';
import toast from 'react-hot-toast';

// Helper to format inline markdown (bold, code, italic)
function formatInline(str) {
  if (!str) return '';
  const parts = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let lastIndex = 0;
  let match;
  let key = 0;

  while ((match = regex.exec(str)) !== null) {
    if (match.index > lastIndex) {
      parts.push(str.substring(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(
        <strong key={key++} className="font-semibold text-white">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code key={key++} className="bg-[#1E293B]/70 text-[#38BDF8] px-1.5 py-0.5 rounded text-xs font-mono">
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(
        <em key={key++} className="italic text-gray-300">
          {token.slice(1, -1)}
        </em>
      );
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < str.length) {
    parts.push(str.substring(lastIndex));
  }

  return parts.length > 0 ? parts : str;
}

// Clean markdown / structured message renderer
function renderFormattedContent(text) {
  if (!text) return null;

  // Sanitize out any leaked internal action strings or tool calls
  const sanitized = text
    .replace(/^(?:svg)?Action:\s*[a-zA-Z0-9_]+\s*\n?/gim, '')
    .replace(/\{"tool":\s*"[^"]+".*?\}/gs, '')
    .trim();

  const lines = sanitized.split('\n');
  const elements = [];
  let currentList = null; // { type: 'ul' | 'ol', items: [] }
  let inKeyValGroup = false;

  const flushList = () => {
    if (currentList) {
      if (currentList.type === 'ul') {
        elements.push(
          <ul key={`ul-${elements.length}`} className="my-2 space-y-1.5 pl-1">
            {currentList.items.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-gray-200">
                <span className="text-[#38BDF8] mt-1.5 text-xs select-none leading-none">•</span>
                <span className="flex-1">{formatInline(item)}</span>
              </li>
            ))}
          </ul>
        );
      } else {
        elements.push(
          <ol key={`ol-${elements.length}`} className="my-2 space-y-1.5 pl-1">
            {currentList.items.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-gray-200">
                <span className="text-[#38BDF8] font-mono text-xs mt-0.5 select-none">{i + 1}.</span>
                <span className="flex-1">{formatInline(item)}</span>
              </li>
            ))}
          </ol>
        );
      }
      currentList = null;
    }
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();

    if (!trimmed) {
      flushList();
      inKeyValGroup = false;
      return;
    }

    // 1. Explicit bullet item (- , * , • )
    const bulletMatch = trimmed.match(/^[-*•]\s+(.+)/);
    if (bulletMatch) {
      if (!currentList || currentList.type !== 'ul') {
        flushList();
        currentList = { type: 'ul', items: [] };
      }
      currentList.items.push(bulletMatch[1]);
      inKeyValGroup = false;
      return;
    }

    // 2. Numbered item (1. , 2. )
    const numberMatch = trimmed.match(/^\d+\.\s+(.+)/);
    if (numberMatch) {
      if (!currentList || currentList.type !== 'ol') {
        flushList();
        currentList = { type: 'ol', items: [] };
      }
      currentList.items.push(numberMatch[1]);
      inKeyValGroup = false;
      return;
    }

    // 3. Header ending with colon (e.g. "Today's earnings:" or "Driver Earnings Overview:")
    const isHeading = trimmed.endsWith(':') && trimmed.length < 70 && !trimmed.includes('http');
    if (isHeading) {
      flushList();
      elements.push(
        <div key={`heading-${index}`} className="font-semibold text-white mt-2.5 mb-1.5 text-sm">
          {formatInline(trimmed.replace(/:$/, ''))}
        </div>
      );
      inKeyValGroup = true;
      return;
    }

    // 4. Key-value item under a header (e.g. "Completed rides: 4", "Total: ₹520")
    const keyValMatch = trimmed.match(/^([A-Za-z0-9\s/_-]{2,30}:\s+.+)$/);
    if (inKeyValGroup && keyValMatch) {
      if (!currentList || currentList.type !== 'ul') {
        flushList();
        currentList = { type: 'ul', items: [] };
      }
      currentList.items.push(keyValMatch[1]);
      return;
    }

    // Normal paragraph
    flushList();
    inKeyValGroup = false;
    elements.push(
      <p key={`p-${index}`} className="my-1 text-gray-200 leading-relaxed">
        {formatInline(trimmed)}
      </p>
    );
  });

  flushList();

  return elements.length > 0 ? elements : <p className="leading-relaxed">{text}</p>;
}

export default function DriverCopilot() {
  const [briefing, setBriefing] = useState(null);
  const [loadingBriefing, setLoadingBriefing] = useState(true);
  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: 'copilot',
      text: "Hello Captain! I'm your RideNow Driver AI Copilot. I'm actively monitoring road conditions, trip surge zones, and your daily earnings. How can I optimize your route or shift right now?",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [sending, setSending] = useState(false);
  const chatEndRef = useRef(null);

  const quickPrompts = [
    "What are my earnings today?",
    "Show my active ride",
    "Give me a route tip",
    "Summarize my driving activity",
  ];

  useEffect(() => {
    loadBriefing();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  const loadBriefing = async () => {
    try {
      setLoadingBriefing(true);
      const res = await getDriverBriefing();
      setBriefing(res);
    } catch (err) {
      console.error('Failed to load driver briefing:', err);
      toast.error('Unable to fetch live briefing');
    } finally {
      setLoadingBriefing(false);
    }
  };

  const handleSendMessage = async (textToSend) => {
    const text = textToSend || inputMessage.trim();
    if (!text || sending) return;

    const userMsg = {
      id: Date.now(),
      sender: 'driver',
      text: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages(prev => [...prev, userMsg]);
    setInputMessage('');
    setSending(true);

    try {
      const res = await chatDriverCopilot(text);
      const copilotReply = {
        id: Date.now() + 1,
        sender: 'copilot',
        text: res.reply || "Advice generated for your route.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages(prev => [...prev, copilotReply]);
      if (res.briefing_snapshot) {
        setBriefing(res.briefing_snapshot);
      }
    } catch (err) {
      console.error('Copilot request failed:', err);
      toast.error("Sorry, I couldn't process that request. Please try again.");
      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: 'copilot',
          text: "Sorry, I couldn't process that request. Please try again.",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    toast.success('Conversation cleared');
  };

  return (
    <div className="space-y-6 animate-fade-in pb-28">
      {/* 1. Header Banner */}
      <div className="card-panel relative overflow-hidden bg-gradient-to-r from-[#0D141B] via-[#101820] to-[#0A0F14] border border-[#1E293B] rounded-2xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <h1 className="text-2xl font-bold text-[#F5F7FA] tracking-tight">
              Driver AI Copilot
            </h1>
            <span className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Active Telemetry
            </span>
          </div>
          <p className="text-gray-400 text-xs sm:text-sm">
            Your intelligent driving assistant for real-time demand, route tips, and earnings optimization.
          </p>
        </div>

        {briefing && (
          <div className="flex items-center gap-3">
            <div className="bg-[#101820] border border-[#1E293B] rounded-xl px-4 py-2 text-right">
              <span className="text-[11px] text-gray-400 block font-medium">Vehicle Unit</span>
              <span className="text-sm font-semibold text-white">{briefing.vehicle || 'Standard Fleet'}</span>
            </div>
            <div className="bg-[#101820] border border-[#1E293B] rounded-xl px-4 py-2 text-right">
              <span className="text-[11px] text-gray-400 block font-medium">Today's Total</span>
              <span className="text-sm font-bold text-emerald-400">{briefing.earnings?.today || '₹0.00'}</span>
            </div>
          </div>
        )}
      </div>

      {/* Main Grid: Copilot Chat + Tactical Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* Left: Interactive Conversational Chat Interface (7 Cols) */}
        <div className="lg:col-span-7 flex flex-col h-[650px] card-panel p-0 overflow-hidden border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-xl">
          
          {/* Chat Panel Header */}
          <div className="p-4 border-b border-[#1E293B] flex items-center justify-between bg-[#101820]/60 shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-[#38BDF8]/10 border border-[#38BDF8]/30 flex items-center justify-center text-[#38BDF8] shadow-[0_0_12px_rgba(56,189,248,0.2)]">
                <Bot className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">AI Copilot</h2>
                <div className="flex items-center gap-1.5 text-[11px] text-emerald-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Your intelligent driving assistant
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                onClick={loadBriefing}
                disabled={loadingBriefing}
                className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white px-2.5 py-1.5 rounded-lg border border-[#1E293B] bg-[#101820] hover:border-[#38BDF8]/30 transition-colors"
                title="Refresh Shift Telemetry"
              >
                <RotateCcw className={`w-3.5 h-3.5 ${loadingBriefing ? 'animate-spin text-[#38BDF8]' : ''}`} />
                <span className="hidden sm:inline">Refresh</span>
              </button>
              <button
                onClick={handleClearChat}
                className="p-1.5 text-gray-400 hover:text-red-400 bg-[#101820] border border-[#1E293B] hover:border-red-500/30 rounded-lg transition-colors"
                title="Clear Chat Conversation"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Chat Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 no-scrollbar bg-[#05070A]/40 flex flex-col">
            {messages.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-6 my-auto">
                <div className="w-12 h-12 rounded-2xl bg-[#38BDF8]/10 border border-[#38BDF8]/30 flex items-center justify-center text-[#38BDF8] mb-3 shadow-[0_0_20px_rgba(56,189,248,0.2)]">
                  <Bot size={24} />
                </div>
                <h3 className="text-base font-bold text-white mb-1">AI Copilot</h3>
                <p className="text-xs text-gray-400 max-w-sm mb-6">
                  Ask me anything about your rides, earnings, routes, drivers, or RideNow.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-md">
                  {quickPrompts.map((prompt, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendMessage(prompt)}
                      disabled={sending}
                      className="text-left text-xs bg-[#101820] hover:bg-[#15222E] hover:border-[#38BDF8]/40 text-gray-300 hover:text-white p-3 rounded-xl border border-[#1E293B] transition flex items-center justify-between group shadow-sm"
                    >
                      <span>{prompt}</span>
                      <ArrowRight size={13} className="text-gray-500 group-hover:text-[#38BDF8] shrink-0 ml-2 transition-colors" />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m) => {
                const isDriver = m.sender === 'driver' || m.role === 'user';
                return (
                  <div
                    key={m.id}
                    className={`flex gap-3 ${isDriver ? 'justify-end' : 'justify-start'}`}
                  >
                    {!isDriver && (
                      <div className="w-8 h-8 rounded-xl bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                        <Bot size={16} />
                      </div>
                    )}

                    <div
                      className={`max-w-[82%] sm:max-w-[78%] rounded-2xl px-4 py-3 text-sm leading-relaxed border ${
                        isDriver
                          ? 'bg-[#38BDF8] text-[#05070A] font-medium border-[#38BDF8] rounded-br-none shadow-[0_2px_15px_rgba(56,189,248,0.25)]'
                          : 'bg-[#101820] text-[#F5F7FA] border-[#1E293B] rounded-bl-none shadow-sm'
                      }`}
                    >
                      {isDriver ? (
                        <p className="whitespace-pre-wrap font-medium">{m.text}</p>
                      ) : (
                        <div className="space-y-1">{renderFormattedContent(m.text)}</div>
                      )}

                      <span
                        className={`block text-[10px] mt-1.5 font-mono ${
                          isDriver ? 'text-[#05070A]/70 text-right' : 'text-gray-500 text-left'
                        }`}
                      >
                        {m.timestamp}
                      </span>
                    </div>

                    {isDriver && (
                      <div className="w-8 h-8 rounded-xl bg-[#101820] border border-[#1E293B] text-gray-300 flex items-center justify-center shrink-0 mt-0.5">
                        <User size={16} />
                      </div>
                    )}
                  </div>
                );
              })
            )}

            {sending && (
              <div className="flex gap-3 justify-start items-start">
                <div className="w-8 h-8 rounded-xl bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                  <Bot size={16} />
                </div>
                <div className="bg-[#101820] border border-[#1E293B] rounded-2xl rounded-bl-none px-4 py-3 shadow-sm flex items-center gap-2.5">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-[#38BDF8] animate-bounce" />
                    <span className="w-2 h-2 rounded-full bg-[#38BDF8] animate-bounce [animation-delay:0.15s]" />
                    <span className="w-2 h-2 rounded-full bg-[#38BDF8] animate-bounce [animation-delay:0.3s]" />
                  </div>
                  <span className="text-xs text-gray-400 font-medium">AI Copilot is thinking...</span>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Quick Prompts Chip Bar */}
          {messages.length > 0 && (
            <div className="px-4 py-2 bg-[#0A0F14] border-t border-[#1E293B] flex items-center gap-2 overflow-x-auto no-scrollbar shrink-0">
              {quickPrompts.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(p)}
                  disabled={sending}
                  className="text-xs whitespace-nowrap bg-[#101820] hover:bg-[#15222E] hover:border-[#38BDF8]/50 text-gray-300 hover:text-[#38BDF8] font-medium px-3 py-1.5 rounded-full border border-[#1E293B] transition shrink-0"
                >
                  {p}
                </button>
              ))}
            </div>
          )}

          {/* Input Box Composer */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="p-3 md:p-4 bg-[#0A0F14] border-t border-[#1E293B] flex items-center gap-2.5 shrink-0"
          >
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              placeholder="Ask Copilot about demand, navigation advice, or earnings..."
              disabled={sending}
              className="flex-1 bg-[#101820] border border-[#1E293B] focus:border-[#38BDF8] rounded-xl px-4 py-2.5 text-sm text-[#F5F7FA] placeholder-gray-500 focus:outline-none transition-colors"
            />
            <button
              type="submit"
              disabled={!inputMessage.trim() || sending}
              className="btn btn-primary h-10 px-4 rounded-xl disabled:opacity-40 shadow-glow flex items-center justify-center gap-1.5 shrink-0"
            >
              <span className="hidden sm:inline text-xs font-bold">Send</span>
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>

        {/* Right Sidebar: Shift Telemetry & Hotspots (5 Cols) */}
        <div className="lg:col-span-5 space-y-6 flex flex-col">
          {/* Surge & Demand Hotspots */}
          <div className="card p-5 border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-lg">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Flame className="w-4 h-4 text-orange-400" />
                <h3 className="text-sm font-semibold text-[#F5F7FA]">ML Demand Hotspots</h3>
              </div>
              <span className="text-[10px] text-[#38BDF8] bg-[#38BDF8]/10 px-2 py-0.5 rounded font-mono font-bold">ML Predictive Surge</span>
            </div>

            {loadingBriefing ? (
              <div className="py-6 text-center text-xs text-gray-400">Loading demand sectors...</div>
            ) : briefing?.demand_zones && briefing.demand_zones.length > 0 ? (
              <div className="space-y-3">
                {briefing.demand_zones.map((zone, idx) => (
                  <div
                    key={idx}
                    className="p-3.5 rounded-xl bg-[#101820] border border-[#1E293B] hover:border-[#38BDF8]/30 transition-colors flex items-center justify-between"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <MapPin className="w-3.5 h-3.5 text-[#38BDF8] shrink-0" />
                        <span className="text-xs font-semibold text-[#F5F7FA]">{zone.zone}</span>
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-gray-400 mt-1">
                        <span>ETA: {zone.eta_mins} mins</span>
                        <span>•</span>
                        <span className="text-amber-400 font-medium">{zone.demand_level} Demand</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="text-xs font-bold px-2.5 py-1 rounded-lg bg-orange-500/10 border border-orange-500/20 text-orange-400">
                        {zone.surge_factor}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400">No active surge zones detected nearby.</p>
            )}
          </div>

          {/* Coaching & Safety Tips */}
          <div className="card p-5 border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-lg">
            <div className="flex items-center gap-2 mb-3.5">
              <Lightbulb className="w-4 h-4 text-[#38BDF8]" />
              <h3 className="text-sm font-semibold text-[#F5F7FA]">AI Shift Coaching</h3>
            </div>

            {loadingBriefing ? (
              <div className="py-4 text-center text-xs text-gray-400">Loading tips...</div>
            ) : briefing?.coaching_tips && briefing.coaching_tips.length > 0 ? (
              <div className="space-y-2.5">
                {briefing.coaching_tips.map((tip, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl bg-[#101820] border border-[#1E293B] flex items-start gap-2.5 text-xs text-gray-300 leading-relaxed"
                  >
                    <Compass className="w-3.5 h-3.5 text-[#38BDF8] shrink-0 mt-0.5" />
                    <span>{tip}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400">Drive safely and obey posted speed limits.</p>
            )}
          </div>

          {/* Performance Snapshot */}
          <div className="card p-5 border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-lg">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">
              Performance Snapshot
            </h3>
            <div className="grid grid-cols-2 gap-3 text-center">
              <div className="p-3.5 rounded-xl bg-[#101820] border border-[#1E293B]">
                <span className="text-[11px] text-gray-400">This Week</span>
                <p className="text-lg font-bold text-[#F5F7FA] mt-0.5">{briefing?.earnings?.week || '₹0.00'}</p>
              </div>
              <div className="p-3.5 rounded-xl bg-[#101820] border border-[#1E293B]">
                <span className="text-[11px] text-gray-400">This Month</span>
                <p className="text-lg font-bold text-[#F5F7FA] mt-0.5">{briefing?.earnings?.month || '₹0.00'}</p>
              </div>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
