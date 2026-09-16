import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useLocation } from 'react-router-dom';
import { sendChatMessage, clearChatHistory } from '../../services/chatService';
import VoiceAssistant from '../../components/ai/VoiceAssistant';
import {
  Sparkles,
  Send,
  Bot,
  User,
  Mic,
  Trash2,
  Compass,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';
import toast from 'react-hot-toast';

export default function AIAssistantPage() {
  const { user } = useAuth();
  const location = useLocation();
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' | 'voice'

  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: `Hello ${user?.name?.split(' ')[0] || 'Commander'}. RideNow Mobility Intelligence Core is online and ready. You can query live ride statuses, calculate transparent fares, analyze driver performance, or review platform policies.`,
      tools: [],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState(
    user?.role === 'driver'
      ? ['What are my earnings today?', 'Where is my active ride?', 'Driver cancellation policy', 'Give me a route tip']
      : ['Where is my ride?', 'Estimate fare for 15 km', 'What is the cancellation policy?', 'How do I pay with UPI?']
  );

  const messagesEndRef = useRef(null);

  useEffect(() => {
    // Check if initial query was passed in URL params (e.g., from Dashboard quick chips)
    const params = new URLSearchParams(location.search);
    const q = params.get('q');
    if (q) {
      handleSend(q);
    }
  }, [location.search]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (queryText) => {
    const text = queryText || input;
    if (!text.trim() || loading) return;

    const userMsg = {
      id: String(Date.now()),
      role: 'user',
      content: text.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const response = await sendChatMessage(text.trim());
      const botMsg = {
        id: String(Date.now() + 1),
        role: 'assistant',
        content: response.reply,
        tools: response.tools_executed || [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, botMsg]);
      if (response.suggested_actions && response.suggested_actions.length > 0) {
        setSuggestions(response.suggested_actions);
      }
    } catch (err) {
      toast.error('AI Core Communication Error');
      setMessages((prev) => [
        ...prev,
        {
          id: String(Date.now() + 1),
          role: 'assistant',
          content: 'I encountered an error querying the intelligence engine. Please retry your request.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = async () => {
    try {
      await clearChatHistory();
      setMessages([
        {
          id: String(Date.now()),
          role: 'assistant',
          content: 'Context buffer reset. How may I assist your transit today?',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
      toast.success('Context reset');
    } catch (err) {
      toast.error('Failed to clear context');
    }
  };

  return (
    <div className={`max-w-4xl mx-auto ${
      activeTab === 'voice' 
        ? 'min-h-[calc(100vh-140px)] flex flex-col gap-4 pb-20 md:pb-8' 
        : 'h-[calc(100vh-140px)] flex flex-col gap-4'
    }`}>
      {/* Page Header */}
      <div className="flex items-center justify-between border-b border-[#1E293B] pb-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#38BDF8]/10 border border-[#38BDF8]/40 flex items-center justify-center text-[#38BDF8] shadow-[0_0_15px_rgba(56,189,248,0.3)]">
            <Sparkles size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-[#F5F7FA]">Nova AI Command Center</h1>
              <span className="text-[10px] font-mono uppercase bg-[#38BDF8]/10 text-[#38BDF8] border border-[#38BDF8]/30 px-2 py-0.5 rounded-full flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] animate-ping"></span>
                GROQ ONLINE
              </span>
            </div>
            <p className="text-xs text-gray-400">Conversational Intelligence · Controlled Tools · LiveKit Voice</p>
          </div>
        </div>

        {/* Mode Switcher */}
        <div className="flex items-center gap-2">
          <div className="bg-[#101820] border border-[#1E293B] rounded-xl p-1 flex items-center gap-1">
            <button
              onClick={() => setActiveTab('chat')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'chat'
                  ? 'bg-[#38BDF8] text-[#05070A] shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Text Core
            </button>
            <button
              onClick={() => setActiveTab('voice')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'voice'
                  ? 'bg-[#38BDF8] text-[#05070A] shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Mic size={14} />
              <span>Voice Core</span>
            </button>
          </div>

          <button
            onClick={handleClear}
            className="p-2 text-gray-400 hover:text-red-400 bg-[#101820] border border-[#1E293B] hover:border-red-500/40 rounded-xl transition-colors"
            title="Reset Context Buffer"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>

      {/* Main Container */}
      <div className={`flex-1 card border border-[#1E293B] bg-[#0A0F14] flex flex-col ${
        activeTab === 'voice' ? 'overflow-y-auto' : 'overflow-hidden'
      } relative shadow-2xl`}>
        {activeTab === 'voice' ? (
          <div className="flex-1 flex flex-col items-center p-6 md:p-8 pb-20 bg-[#05070A]/50 w-full overflow-y-auto">
            <div className="my-auto w-full flex flex-col items-center">
              <VoiceAssistant onClose={() => setActiveTab('chat')} />
            </div>
          </div>
        ) : (
          <>
            {/* Messages Scroll Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4 no-scrollbar bg-[#05070A]/40">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {m.role === 'assistant' && (
                    <div className="w-8 h-8 rounded-xl bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                      <Bot size={16} />
                    </div>
                  )}

                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed border ${
                      m.role === 'user'
                        ? 'bg-[#38BDF8] text-[#05070A] font-semibold border-[#38BDF8] rounded-br-none shadow-[0_2px_15px_rgba(56,189,248,0.25)]'
                        : 'bg-[#101820] text-[#F5F7FA] border-[#1E293B] rounded-bl-none shadow-sm'
                    }`}
                  >
                    <div className="whitespace-pre-wrap font-normal">{m.content}</div>

                    <span
                      className={`block text-[10px] mt-1 font-mono ${
                        m.role === 'user' ? 'text-[#05070A]/70 text-right' : 'text-gray-500 text-left'
                      }`}
                    >
                      {m.timestamp}
                    </span>
                  </div>

                  {m.role === 'user' && (
                    <div className="w-8 h-8 rounded-xl bg-[#101820] border border-[#1E293B] text-gray-300 flex items-center justify-center shrink-0 mt-0.5">
                      <User size={16} />
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div className="flex gap-3 justify-start">
                  <div className="w-8 h-8 rounded-xl bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center shrink-0">
                    <Bot size={16} className="animate-spin" />
                  </div>
                  <div className="bg-[#101820] border border-[#1E293B] rounded-2xl rounded-bl-none px-4 py-3 shadow-sm flex items-center gap-1.5">
                    <div className="w-2 h-2 rounded-full bg-[#38BDF8] animate-bounce"></div>
                    <div
                      className="w-2 h-2 rounded-full bg-[#38BDF8] animate-bounce"
                      style={{ animationDelay: '0.15s' }}
                    ></div>
                    <div
                      className="w-2 h-2 rounded-full bg-[#38BDF8] animate-bounce"
                      style={{ animationDelay: '0.3s' }}
                    ></div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Quick Suggestions Chips */}
            {suggestions.length > 0 && (
              <div className="px-4 py-2.5 bg-[#0A0F14] border-t border-[#1E293B] flex items-center gap-2 overflow-x-auto no-scrollbar">
                {suggestions.map((s, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSend(s)}
                    className="text-xs whitespace-nowrap bg-[#101820] hover:bg-[#15222E] hover:border-[#38BDF8]/50 text-gray-300 hover:text-[#38BDF8] font-medium px-3 py-1.5 rounded-full border border-[#1E293B] transition shrink-0"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}

            {/* Input Bar */}
            <div className="p-4 bg-[#0A0F14] border-t border-[#1E293B]">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSend();
                }}
                className="flex items-center gap-3"
              >
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask Nova about rides, fare estimates, traffic tips, or policies..."
                  className="input-field text-sm flex-1 bg-[#101820]"
                />
                <button
                  type="submit"
                  disabled={!input.trim() || loading}
                  className="btn btn-primary h-12 px-6 rounded-xl text-sm font-bold flex items-center gap-2"
                >
                  <span>Dispatch</span>
                  <Send size={16} />
                </button>
              </form>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
