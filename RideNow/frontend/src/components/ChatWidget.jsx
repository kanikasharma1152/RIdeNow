import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { sendChatMessage, clearChatHistory } from '../services/chatService';
import VoiceAssistant from './ai/VoiceAssistant';
import {
  MessageSquare,
  X,
  Send,
  Sparkles,
  Bot,
  User,
  Trash2,
  Minimize2,
  Mic,
  CheckCircle,
  Clock,
  Compass,
  Car,
  ArrowRight,
} from 'lucide-react';
import toast from 'react-hot-toast';

export default function ChatWidget() {
  const { user } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' | 'voice'
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: `Hello ${user?.name?.split(' ')[0] || 'Commander'}. Nova AI Mobility Core active. I can assist with active rides, route optimization, fare estimation, or platform policies.`,
      tools: [],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState(
    user?.role === 'driver'
      ? ['What are my earnings today?', 'Where is my active ride?', 'Driver cancellation policy']
      : ['Where is my ride?', 'Estimate fare for 15 km', 'What is the cancellation policy?']
  );

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen && activeTab === 'chat') {
      scrollToBottom();
    }
  }, [messages, isOpen, activeTab]);

  const handleSend = async (textToSend) => {
    const query = textToSend || input;
    if (!query.trim() || loading) return;

    const userMessage = {
      id: String(Date.now()),
      role: 'user',
      content: query.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await sendChatMessage(query.trim());

      const bookTool = (response.tools_executed || []).find((t) => t.tool === 'book_ride');
      const bookingResult = bookTool?.result?.success ? bookTool.result : null;

      const botMessage = {
        id: String(Date.now() + 1),
        role: 'assistant',
        content: response.reply,
        tools: response.tools_executed || [],
        bookingResult: bookingResult,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, botMessage]);
      if (response.suggested_actions && response.suggested_actions.length > 0) {
        setSuggestions(response.suggested_actions);
      }
    } catch (err) {
      toast.error(err.message || 'Failed to communicate with AI core');
      setMessages((prev) => [
        ...prev,
        {
          id: String(Date.now() + 1),
          role: 'assistant',
          content: 'I encountered an issue querying the intelligence service. Please try again.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleClearHistory = async () => {
    try {
      await clearChatHistory();
      setMessages([
        {
          id: String(Date.now()),
          role: 'assistant',
          content: 'Context buffer reset. How can I assist your journey now?',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
      toast.success('AI conversation context cleared');
    } catch (err) {
      toast.error('Failed to clear context');
    }
  };

  if (!user) return null;

  return (
    <div className="fixed bottom-20 md:bottom-6 right-4 md:right-6 z-40 flex flex-col items-end">
      {/* Expanded AI Command Shell */}
      {isOpen && (
        <div className="mb-4 w-96 max-w-[calc(100vw-2rem)] h-[560px] max-h-[85vh] bg-[#0A0F14] rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.8)] border border-[#1E293B] flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-5 duration-200">
          {/* Command Center Header */}
          <div className="bg-[#101820] border-b border-[#1E293B] px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-[#38BDF8]/10 border border-[#38BDF8]/40 flex items-center justify-center text-[#38BDF8]">
                <Sparkles className="w-4 h-4 animate-pulse" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-sm leading-none text-[#F5F7FA]">Nova AI</h3>
                  <span className="flex items-center gap-1 text-[10px] bg-[#38BDF8]/10 text-[#38BDF8] font-mono px-2 py-0.5 rounded-full border border-[#38BDF8]/30">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] animate-ping"></span>
                    ONLINE
                  </span>
                </div>
                <p className="text-[11px] text-gray-400 mt-0.5 font-mono">INTELLIGENT CORE</p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              {/* Tab Selector: Chat or Voice */}
              <button
                onClick={() => setActiveTab(activeTab === 'chat' ? 'voice' : 'chat')}
                className={`p-1.5 rounded-lg border transition-colors ${
                  activeTab === 'voice'
                    ? 'bg-[#38BDF8] text-[#05070A] border-[#38BDF8]'
                    : 'text-gray-400 border-transparent hover:text-white hover:bg-white/5'
                }`}
                title={activeTab === 'chat' ? "Switch to Voice Mode" : "Switch to Chat Mode"}
              >
                <Mic className="w-4 h-4" />
              </button>
              <button
                onClick={handleClearHistory}
                title="Clear context"
                className="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-white/5 transition"
              >
                <Trash2 className="w-4 h-4" />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-white/5 transition"
              >
                <Minimize2 className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Body: Either Chat Stream or Voice Core */}
          {activeTab === 'voice' ? (
            <div className="flex-1 flex flex-col items-center bg-[#05070A]/50 overflow-y-auto p-4 pb-12">
              <div className="my-auto w-full flex flex-col items-center">
                <VoiceAssistant onClose={() => setActiveTab('chat')} />
              </div>
            </div>
          ) : (
            <>
              {/* Message Stream */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3.5 bg-[#05070A]/40 no-scrollbar">
                {messages.map((m) => (
                  <div
                    key={m.id}
                    className={`flex gap-2.5 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    {m.role === 'assistant' && (
                      <div className="w-7 h-7 rounded-full bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                        <Bot className="w-3.5 h-3.5" />
                      </div>
                    )}

                    <div
                      className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed border ${
                        m.role === 'user'
                          ? 'bg-[#38BDF8] text-[#05070A] font-medium border-[#38BDF8] rounded-br-none shadow-[0_2px_10px_rgba(56,189,248,0.2)]'
                          : 'bg-[#101820] text-[#F5F7FA] border-[#1E293B] rounded-bl-none shadow-sm'
                      }`}
                    >
                      <div className="whitespace-pre-wrap font-normal">{m.content}</div>

                      {/* Booking Confirmation Card */}
                      {m.bookingResult && (
                        <div className="mt-2.5 p-3 rounded-xl bg-[#0A0F14] border border-[#38BDF8]/40 shadow-md text-[#F5F7FA]">
                          <div className="flex items-center justify-between mb-1.5 border-b border-[#1E293B] pb-1">
                            <span className="text-[11px] font-bold text-[#38BDF8] flex items-center gap-1">
                              <Car size={13} /> RIDE BOOKED #{m.bookingResult.ride_id}
                            </span>
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-[#38BDF8] text-[#05070A]">
                              {m.bookingResult.status}
                            </span>
                          </div>
                          <div className="space-y-1 text-[11px] text-gray-300">
                            <div><span className="text-gray-500">Pickup:</span> {m.bookingResult.pickup}</div>
                            <div><span className="text-gray-500">Destination:</span> {m.bookingResult.dropoff}</div>
                            <div><span className="text-gray-500">Fare:</span> <span className="font-mono font-bold text-emerald-400">₹{m.bookingResult.fare}</span></div>
                          </div>
                          <Link
                            to={`/rides/${m.bookingResult.ride_id}`}
                            onClick={() => setIsOpen(false)}
                            className="mt-2.5 w-full btn btn-primary py-1.5 text-[10px] font-bold uppercase tracking-wider flex items-center justify-center gap-1"
                          >
                            <span>Track Live Ride</span>
                            <ArrowRight size={12} />
                          </Link>
                        </div>
                      )}

                      <span
                        className={`block text-[10px] mt-1 font-mono ${
                          m.role === 'user' ? 'text-[#05070A]/70 text-right' : 'text-gray-500 text-left'
                        }`}
                      >
                        {m.timestamp}
                      </span>
                    </div>

                    {m.role === 'user' && (
                      <div className="w-7 h-7 rounded-full bg-[#101820] border border-[#1E293B] text-gray-300 flex items-center justify-center shrink-0 mt-0.5">
                        <User className="w-3.5 h-3.5" />
                      </div>
                    )}
                  </div>
                ))}

                {loading && (
                  <div className="flex gap-2.5 justify-start">
                    <div className="w-7 h-7 rounded-full bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center shrink-0">
                      <Bot className="w-3.5 h-3.5 animate-spin" />
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
                <div className="px-3 py-2 bg-[#0A0F14] border-t border-[#1E293B] flex items-center gap-1.5 overflow-x-auto no-scrollbar">
                  {suggestions.map((s, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSend(s)}
                      className="text-[11px] whitespace-nowrap bg-[#101820] hover:bg-[#15222E] hover:border-[#38BDF8]/50 text-gray-300 hover:text-[#38BDF8] font-medium px-2.5 py-1 rounded-full border border-[#1E293B] transition shrink-0"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}

              {/* Input Bar */}
              <div className="p-3 bg-[#0A0F14] border-t border-[#1E293B]">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSend();
                  }}
                  className="flex items-center gap-2"
                >
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Command Nova AI..."
                    className="flex-1 text-sm bg-[#101820] border border-[#1E293B] rounded-xl px-3.5 py-2.5 text-[#F5F7FA] placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-[#38BDF8] focus:border-[#38BDF8] transition"
                  />
                  <button
                    type="submit"
                    disabled={!input.trim() || loading}
                    className="w-10 h-10 rounded-xl bg-[#38BDF8] hover:bg-[#5CC8FF] disabled:opacity-30 text-[#05070A] flex items-center justify-center transition shadow-[0_0_15px_rgba(56,189,248,0.3)] shrink-0 font-bold"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </form>
              </div>
            </>
          )}
        </div>
      )}

      {/* Floating Launcher Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="group relative flex items-center justify-center w-14 h-14 rounded-full bg-[#0A0F14] border-2 border-[#38BDF8] text-[#38BDF8] shadow-[0_0_25px_rgba(56,189,248,0.4)] hover:scale-105 active:scale-95 transition-all duration-200"
        aria-label="Open AI Assistant"
      >
        {isOpen ? (
          <X className="w-6 h-6 transition-transform duration-200 text-[#F5F7FA]" />
        ) : (
          <>
            <Sparkles className="w-6 h-6 group-hover:rotate-12 transition-transform duration-300" />
            <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-[#38BDF8] border-2 border-[#05070A] rounded-full animate-ping"></span>
            <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-[#38BDF8] border-2 border-[#05070A] rounded-full"></span>
          </>
        )}
      </button>
    </div>
  );
}
