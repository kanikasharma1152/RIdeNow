import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useLocation, Link } from 'react-router-dom';
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
  Camera,
  Car,
  X,
  MapPin,
  CheckCircle2,
  Navigation,
  Loader2,
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
      content: `Hello ${user?.name?.split(' ')[0] || 'Passenger'}. RideNow Multimodal Mobility Core is online. You can type, speak, attach photos/map screenshots, share your GPS location, calculate transparent fares, or book rides in English, Hindi, and Hinglish.`,
      tools: [],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [aiState, setAiState] = useState('IDLE'); // 'IDLE' | 'ANALYZING_IMAGE' | 'CALCULATING_ROUTE' | 'THINKING'
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [userLocation, setUserLocation] = useState(null);
  const fileInputRef = useRef(null);

  const [suggestions, setSuggestions] = useState(
    user?.role === 'driver'
      ? ['What are my earnings today?', 'Where is my active ride?', 'Driver cancellation policy', 'Give me a route tip']
      : ['Where is my ride?', 'Book a ride to Railway Station', 'Estimate fare for 15 km', 'If I cancel my ride will I be charged?']
  );

  const messagesEndRef = useRef(null);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const q = params.get('q');
    if (q) {
      handleSend(q);
    }
  }, [location.search]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleImageSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      toast.error('Image size must be under 10MB');
      return;
    }
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = () => setImagePreview(reader.result);
    reader.readAsDataURL(file);
    toast.success('Photo attached');
  };

  const removeImage = () => {
    setImageFile(null);
    setImagePreview(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleShareLocation = () => {
    if (userLocation) {
      setUserLocation(null);
      toast('GPS location unattached');
      return;
    }
    if ('geolocation' in navigator) {
      toast.loading('Acquiring GPS coordinates...', { id: 'gps-loc' });
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
          toast.success('GPS coordinates attached', { id: 'gps-loc' });
        },
        (err) => {
          toast.error('Unable to retrieve location', { id: 'gps-loc' });
        },
        { enableHighAccuracy: true, timeout: 6000 }
      );
    } else {
      toast.error('Geolocation not supported on this browser');
    }
  };

  const handleSend = async (queryText) => {
    const text = (queryText || input).trim();
    if (!text && !imagePreview) return;
    if (loading) return;

    const currentImg = imagePreview;
    removeImage();

    // Determine state indicator
    if (currentImg) {
      setAiState('ANALYZING_IMAGE');
    } else if (text.toLowerCase().includes('fare') || text.toLowerCase().includes('book') || text.toLowerCase().includes('how much')) {
      setAiState('CALCULATING_ROUTE');
    } else {
      setAiState('THINKING');
    }

    const userMsg = {
      id: String(Date.now()),
      role: 'user',
      content: text || 'Location photo attached',
      imagePreview: currentImg,
      locationAttached: userLocation ? `${userLocation.lat.toFixed(4)}, ${userLocation.lng.toFixed(4)}` : null,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const response = await sendChatMessage(text || 'Identify this location', {
        imageBase64: currentImg,
        latitude: userLocation?.lat,
        longitude: userLocation?.lng,
      });

      // Check if book_ride succeeded
      const bookTool = (response.tools_executed || []).find((t) => t.tool === 'book_ride');
      const bookingResult = bookTool?.result?.success ? bookTool.result : null;

      const botMsg = {
        id: String(Date.now() + 1),
        role: 'assistant',
        content: response.reply,
        tools: response.tools_executed || [],
        bookingResult: bookingResult,
        visualContext: response.visual_context,
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
          content: 'I encountered an issue querying the intelligence engine. Please try again.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setLoading(false);
      setAiState('IDLE');
    }
  };

  const handleClear = async () => {
    try {
      await clearChatHistory();
      setUserLocation(null);
      setMessages([
        {
          id: String(Date.now()),
          role: 'assistant',
          content: 'Conversation context reset. How may I assist your transit today?',
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
        : 'h-[calc(100vh-140px)] flex flex-col gap-4 pb-20 md:pb-8'
    } animate-fade-in`}>
      {/* Header card */}
      <div className="card-panel p-5 rounded-2xl bg-[#0A0F14] border border-[#1E293B] flex flex-wrap items-center justify-between gap-4 shrink-0 shadow-lg">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-[#38BDF8] to-[#0EA5E9] text-[#05070A] flex items-center justify-center shadow-[0_0_20px_rgba(56,189,248,0.3)]">
            <Sparkles size={24} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-[#F5F7FA]">Nova AI Mobility Assistant</h1>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#101820] text-[#38BDF8] border border-[#38BDF8]/30 uppercase font-mono tracking-wider">
                Multimodal Core
              </span>
            </div>
            <p className="text-xs text-gray-400">
              Natural Language Booking · English · Hindi · Hinglish · Context Aware
            </p>
          </div>
        </div>

        {/* Tab & Clear Action */}
        <div className="flex items-center gap-3">
          <div className="flex p-1 bg-[#101820] border border-[#1E293B] rounded-xl">
            <button
              onClick={() => setActiveTab('chat')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'chat'
                  ? 'bg-[#38BDF8] text-[#05070A] shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Text & Vision
            </button>
            <button
              onClick={() => setActiveTab('voice')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                activeTab === 'voice'
                  ? 'bg-[#38BDF8] text-[#05070A] shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Mic size={13} />
              <span>Voice</span>
            </button>
          </div>

          <button
            onClick={handleClear}
            className="p-2.5 rounded-xl bg-[#101820] border border-[#1E293B] text-gray-400 hover:text-red-400 hover:border-red-500/30 transition shadow-sm"
            title="Clear context & history"
            aria-label="Clear chat history"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>

      {/* Main Container */}
      <div className="card-panel p-0 rounded-2xl bg-[#0A0F14] border border-[#1E293B] flex-1 flex flex-col overflow-hidden shadow-xl">
        {activeTab === 'voice' ? (
          <div className="flex-1 p-6 overflow-y-auto">
            <VoiceAssistant />
          </div>
        ) : (
          <>
            {/* Messages Scroll Area */}
            <div className="flex-1 p-6 overflow-y-auto space-y-4">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex gap-3 max-w-[85%] ${
                    m.role === 'user' ? 'ml-auto justify-end' : 'mr-auto justify-start'
                  }`}
                >
                  {m.role === 'assistant' && (
                    <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-[#38BDF8] to-[#0EA5E9] text-[#05070A] flex items-center justify-center shrink-0 mt-0.5 shadow-[0_0_10px_rgba(56,189,248,0.2)]">
                      <Bot size={16} />
                    </div>
                  )}

                  <div
                    className={`rounded-2xl px-4 py-3 shadow-md ${
                      m.role === 'user'
                        ? 'bg-[#38BDF8] text-[#05070A] font-medium rounded-br-none'
                        : 'bg-[#101820] text-[#F5F7FA] border border-[#1E293B] rounded-bl-none'
                    }`}
                  >
                    {/* User Attached Image Preview */}
                    {m.imagePreview && (
                      <div className="mb-2 rounded-xl overflow-hidden border border-black/20 max-w-xs max-h-48">
                        <img src={m.imagePreview} alt="User upload" className="w-full h-auto object-cover" />
                      </div>
                    )}

                    {/* User Location Badge */}
                    {m.locationAttached && (
                      <div className="mb-1.5 flex items-center gap-1 text-[11px] text-[#05070A]/80 font-mono">
                        <MapPin size={12} /> GPS Attached: {m.locationAttached}
                      </div>
                    )}

                    <div className="text-xs sm:text-sm whitespace-pre-wrap leading-relaxed">
                      {m.content}
                    </div>

                    {/* Live Ride Booking Card */}
                    {m.bookingResult && (
                      <div className="mt-3.5 p-3.5 rounded-xl bg-[#0A0F14] border border-[#38BDF8]/40 shadow-lg animate-fade-in">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-1.5 text-[#38BDF8] font-bold text-xs">
                            <Car size={15} />
                            <span>Ride #{m.bookingResult.ride_id} Confirmed</span>
                          </div>
                          <span className="text-[10px] font-mono uppercase bg-[#38BDF8]/10 text-[#38BDF8] px-2 py-0.5 rounded border border-[#38BDF8]/20">
                            {m.bookingResult.status}
                          </span>
                        </div>

                        <div className="space-y-1.5 text-xs text-gray-300">
                          <div className="flex items-start gap-1.5">
                            <span className="text-gray-500 w-16 shrink-0">Pickup:</span>
                            <span className="font-semibold text-gray-200">{m.bookingResult.pickup}</span>
                          </div>
                          <div className="flex items-start gap-1.5">
                            <span className="text-gray-500 w-16 shrink-0">Dropoff:</span>
                            <span className="font-semibold text-gray-200">{m.bookingResult.dropoff}</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className="text-gray-500 w-16 shrink-0">Fare:</span>
                            <span className="font-mono font-bold text-emerald-400">₹{m.bookingResult.fare}</span>
                          </div>
                        </div>

                        <Link
                          to={`/rides/${m.bookingResult.ride_id}`}
                          className="mt-3 w-full btn btn-primary py-2 text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-1.5 shadow-[0_0_15px_rgba(56,189,248,0.25)]"
                        >
                          <span>Track Live Ride</span>
                          <ArrowRight size={14} />
                        </Link>
                      </div>
                    )}

                    <span
                      className={`block text-[10px] mt-1.5 font-mono ${
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
                <div className="flex gap-3 justify-start items-center">
                  <div className="w-8 h-8 rounded-xl bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center shrink-0">
                    <Bot size={16} className="animate-spin" />
                  </div>
                  <div className="bg-[#101820] border border-[#1E293B] rounded-2xl rounded-bl-none px-4 py-2.5 shadow-sm flex items-center gap-2 text-xs text-gray-400">
                    <Loader2 size={14} className="animate-spin text-[#38BDF8]" />
                    <span>
                      {aiState === 'ANALYZING_IMAGE'
                        ? 'Scanning photo landmarks...'
                        : aiState === 'CALCULATING_ROUTE'
                        ? 'Calculating route and transparent fare...'
                        : 'Nova is analyzing your query...'}
                    </span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Quick Suggestions Chips */}
            {suggestions.length > 0 && (
              <div className="px-6 py-2.5 bg-[#0A0F14] border-t border-[#1E293B] flex gap-2 overflow-x-auto no-scrollbar">
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
              {/* Hidden file input */}
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleImageSelect}
                accept="image/*"
                className="hidden"
              />

              {/* Multimodal Attachment Previews */}
              <div className="flex flex-wrap items-center gap-2 mb-2">
                {imagePreview && (
                  <div className="flex items-center gap-2 p-1.5 px-2.5 rounded-xl bg-[#101820] border border-[#38BDF8]/40 text-xs">
                    <img src={imagePreview} alt="Attached" className="w-7 h-7 object-cover rounded border border-[#1E293B]" />
                    <span className="font-semibold text-gray-200 text-[11px]">Photo attached</span>
                    <button
                      type="button"
                      onClick={removeImage}
                      className="p-0.5 text-gray-400 hover:text-red-400 transition-colors ml-1"
                    >
                      <X size={13} />
                    </button>
                  </div>
                )}

                {userLocation && (
                  <div className="flex items-center gap-1.5 p-1.5 px-2.5 rounded-xl bg-[#38BDF8]/15 border border-[#38BDF8]/30 text-xs text-[#38BDF8]">
                    <MapPin size={13} />
                    <span className="font-mono text-[11px]">GPS: {userLocation.lat.toFixed(4)}, {userLocation.lng.toFixed(4)}</span>
                    <button
                      type="button"
                      onClick={() => setUserLocation(null)}
                      className="p-0.5 text-gray-400 hover:text-red-400 transition-colors ml-1"
                    >
                      <X size={13} />
                    </button>
                  </div>
                )}
              </div>

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSend();
                }}
                className="flex items-center gap-2"
              >
                {/* Camera / Image Button */}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className={`p-2.5 rounded-xl border transition ${
                    imageFile
                      ? 'bg-[#38BDF8]/20 border-[#38BDF8] text-[#38BDF8]'
                      : 'bg-[#101820] border-[#1E293B] text-gray-400 hover:text-[#38BDF8] hover:border-[#38BDF8]/40'
                  }`}
                  title="Attach location photo or map screenshot"
                  aria-label="Attach photo"
                >
                  <Camera size={18} />
                </button>

                {/* GPS Location Button */}
                <button
                  type="button"
                  onClick={handleShareLocation}
                  className={`p-2.5 rounded-xl border transition ${
                    userLocation
                      ? 'bg-[#38BDF8]/20 border-[#38BDF8] text-[#38BDF8]'
                      : 'bg-[#101820] border-[#1E293B] text-gray-400 hover:text-[#38BDF8] hover:border-[#38BDF8]/40'
                  }`}
                  title={userLocation ? 'GPS location attached' : 'Attach current location'}
                  aria-label="Attach location"
                >
                  <MapPin size={18} />
                </button>

                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask Nova (e.g. 'Take me to airport', 'how much?', 'book it', 'where is my driver')..."
                  className="input-field text-sm flex-1 bg-[#101820]"
                />
                <button
                  type="submit"
                  disabled={(!input.trim() && !imagePreview) || loading}
                  className="btn btn-primary h-12 px-6 rounded-xl text-sm font-bold flex items-center gap-2 shadow-[0_0_15px_rgba(56,189,248,0.25)]"
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
