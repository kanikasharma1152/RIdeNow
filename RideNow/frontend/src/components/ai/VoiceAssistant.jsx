import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff,
  PhoneOff,
  AlertCircle,
  Loader2,
  Volume2,
  Sparkles,
  Radio,
} from 'lucide-react';
import { Room, RoomEvent, Track } from 'livekit-client';
import { getVoiceToken } from '../../services/voiceService';
import toast from 'react-hot-toast';

export default function VoiceAssistant({ onClose }) {
  // Voice states: 'idle' | 'connecting' | 'connected' | 'listening' | 'speaking' | 'unavailable' | 'error'
  const [state, setState] = useState('idle');
  const [isMuted, setIsMuted] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [transcript, setTranscript] = useState('');

  const roomRef = useRef(null);
  const audioElementsRef = useRef(new Map());

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (roomRef.current) {
        roomRef.current.disconnect();
        roomRef.current = null;
      }
    };
  }, []);

  const startVoiceSession = async () => {
    setState('connecting');
    setErrorMessage('');
    setTranscript('Initializing encrypted LiveKit WebRTC channel...');

    try {
      // 1. Request short-lived token from backend
      const data = await getVoiceToken();
      if (!data || !data.token) {
        throw new Error('Invalid token response from voice service');
      }
      console.log('[VOICE] token received');

      // 2. Initialize LiveKit Room
      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
        audioCaptureDefaults: {
          autoGainControl: true,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      roomRef.current = room;

      // 3. Setup event listeners
      room.on(RoomEvent.Connected, () => {
        console.log('[VOICE] connected');
        setState('listening');
        setTranscript('Connected to Nova AI Core. Listening for your command...');
        toast.success('LiveKit Voice Room Connected');
      });

      room.on(RoomEvent.ParticipantConnected, (participant) => {
        console.log('[VOICE] remote participant joined');
      });

      room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
        if (track.kind === Track.Kind.Audio) {
          console.log('[VOICE] remote audio track subscribed');
          // Play remote audio (Agent Cartesia TTS)
          const element = track.attach();
          element.autoplay = true;
          element.play().catch((playErr) => {
            console.warn('[VOICE] Audio autoplay blocked or requires interaction:', playErr);
          });
          document.body.appendChild(element);
          audioElementsRef.current.set(publication.trackSid, element);
          console.log('[VOICE] remote audio attached');
          setState('speaking');
        }
      });

      room.on(RoomEvent.TrackUnsubscribed, (track, publication) => {
        track.detach();
        const el = audioElementsRef.current.get(publication.trackSid);
        if (el && el.parentNode) {
          el.parentNode.removeChild(el);
        }
        audioElementsRef.current.delete(publication.trackSid);
        setState('listening');
      });

      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        if (speakers.length > 0) {
          const isAgent = speakers.some((s) => !s.isLocal);
          if (isAgent) {
            setState('speaking');
          } else {
            setState('listening');
          }
        }
      });

      room.on(RoomEvent.Disconnected, () => {
        console.log('[VOICE] disconnected');
        setState('idle');
        setTranscript('');
      });

      // 4. Connect to LiveKit Room
      console.log('[VOICE] connecting to LiveKit');
      await room.connect(data.url, data.token);

      // 5. Publish local microphone track
      try {
        await room.localParticipant.setMicrophoneEnabled(true);
        console.log('[VOICE] microphone published');
      } catch (micErr) {
        console.warn('Microphone permission warning:', micErr);
        toast.error('Microphone permission required for voice');
        setErrorMessage('Microphone access denied or unavailable in this browser.');
        setState('error');
        room.disconnect();
        return;
      }

      setState('listening');
    } catch (err) {
      console.error('LiveKit voice connection error:', err);
      if (err.response && err.response.status === 503) {
        setState('unavailable');
        setErrorMessage('Voice interface is not configured on this server.');
      } else {
        setState('error');
        setErrorMessage(err.message || 'Could not establish LiveKit voice session.');
      }
    }
  };

  const toggleMute = async () => {
    if (!roomRef.current || !roomRef.current.localParticipant) return;
    const newMuteState = !isMuted;
    await roomRef.current.localParticipant.setMicrophoneEnabled(!newMuteState);
    setIsMuted(newMuteState);
    toast(newMuteState ? 'Microphone muted' : 'Microphone active');
  };

  const endSession = () => {
    if (roomRef.current) {
      roomRef.current.disconnect();
      roomRef.current = null;
    }
    setState('idle');
    setTranscript('');
    if (onClose) onClose();
  };

  const getPillBadgeClass = () => {
    if (state === 'listening' || state === 'speaking') {
      return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30';
    }
    if (state === 'connecting') {
      return 'bg-[#38BDF8]/10 text-[#38BDF8] border border-[#38BDF8]/30';
    }
    return 'bg-gray-500/10 text-gray-400';
  };

  const getCircleClass = () => {
    if (state === 'speaking') {
      return 'bg-[#101820] border-2 border-emerald-400 text-emerald-400 shadow-[0_0_40px_rgba(16,185,129,0.4)]';
    }
    if (state === 'listening') {
      return 'bg-[#101820] border-2 border-[#38BDF8] text-[#38BDF8]';
    }
    if (state === 'connecting') {
      return 'bg-[#0D141B] border border-[#1E293B] text-[#38BDF8]';
    }
    if (state === 'unavailable' || state === 'error') {
      return 'bg-[#181115] border border-red-500/40 text-red-400';
    }
    return 'bg-[#101820] border border-[#1E293B] text-gray-400 hover:text-white hover:border-[#38BDF8]';
  };

  return (
    <div className="flex flex-col items-center justify-center p-6 text-center space-y-6 max-w-lg mx-auto w-full">
      {/* Live AI Status Pill */}
      <div className="inline-flex items-center gap-2 bg-[#101820] border border-[#1E293B] px-3.5 py-1 rounded-full text-xs font-mono text-gray-300">
        <Radio size={12} className={state === 'listening' || state === 'speaking' ? 'text-emerald-400 animate-pulse' : 'text-gray-500'} />
        <span>CARTESIA + GROQ AI VOICE</span>
        <span className={'text-[10px] px-2 py-0.5 rounded-full uppercase font-bold ' + getPillBadgeClass()}>
          {state === 'listening' ? 'ONLINE' : state === 'speaking' ? 'SPEAKING' : state.toUpperCase()}
        </span>
      </div>

      {/* Visual Pulsing Voice Core */}
      <div className="relative flex items-center justify-center">
        {(state === 'listening' || state === 'speaking') && (
          <div className="absolute w-40 h-40 bg-[#38BDF8]/20 rounded-full animate-ping pointer-events-none"></div>
        )}
        {state === 'speaking' && (
          <div className="absolute w-48 h-48 bg-emerald-500/15 rounded-full animate-pulse pointer-events-none"></div>
        )}
        {state === 'connecting' && (
          <div className="absolute w-36 h-36 border-2 border-[#38BDF8]/40 border-t-[#38BDF8] rounded-full animate-spin pointer-events-none"></div>
        )}

        <div className={'w-32 h-32 rounded-full flex flex-col items-center justify-center transition-all duration-500 shadow-[0_0_35px_rgba(56,189,248,0.3)] ' + getCircleClass()}>
          {state === 'connecting' ? (
            <Loader2 className="w-12 h-12 animate-spin text-[#38BDF8]" />
          ) : state === 'speaking' ? (
            <Volume2 className="w-12 h-12 animate-bounce text-emerald-400" />
          ) : state === 'listening' ? (
            <Mic className="w-12 h-12 animate-pulse text-[#38BDF8]" />
          ) : state === 'unavailable' || state === 'error' ? (
            <AlertCircle className="w-12 h-12 text-red-400" />
          ) : (
            <Mic className="w-12 h-12" />
          )}
        </div>
      </div>

      {/* Voice Status & Subtitles */}
      <div>
        <h4 className="text-xl font-bold text-[#F5F7FA]">
          {state === 'speaking'
            ? 'Nova Speaking...'
            : state === 'listening'
            ? 'Listening to Commander...'
            : state === 'connecting'
            ? 'Connecting Real-Time Pipeline...'
            : state === 'unavailable'
            ? 'Voice Mode Unavailable'
            : state === 'error'
            ? 'Connection Error'
            : 'RideNow AI Voice Core'}
        </h4>
        <p className="text-xs text-gray-400 mt-2 max-w-sm mx-auto leading-relaxed">
          {state === 'listening' || state === 'speaking'
            ? 'Ask: "Where is my active ride?", "Calculate fare for 15 km", or "What is the cancellation policy?"'
            : state === 'unavailable' || state === 'error'
            ? errorMessage
            : 'Stream real-time low-latency audio via Cartesia STT, Groq LLM, and Cartesia TTS directly into the platform.'}
        </p>
      </div>

      {/* Wave Indicator Animation */}
      {(state === 'listening' || state === 'speaking') && (
        <div className="flex items-center justify-center gap-1.5 h-10">
          {[40, 75, 100, 60, 90, 45, 80, 65, 95, 50].map((h, i) => (
            <div
              key={i}
              className={'w-1 rounded-full transition-all duration-300 ' + (state === 'speaking' ? 'bg-emerald-400 animate-pulse' : 'bg-[#38BDF8] animate-bounce')}
              style={{
                height: h + '%',
                animationDelay: (i * 0.1) + 's',
              }}
            ></div>
          ))}
        </div>
      )}

      {/* Live Transcript Box */}
      {transcript && (
        <div className="w-full max-w-md bg-[#0A0F14] border border-[#1E293B] rounded-xl p-3 text-xs font-mono text-gray-400 text-left flex items-start gap-2.5">
          <Sparkles size={14} className="text-[#38BDF8] shrink-0 mt-0.5" />
          <span className="leading-relaxed">{transcript}</span>
        </div>
      )}

      {/* Control Actions */}
      <div className="flex items-center gap-3 pt-2 pb-4">
        {state === 'idle' ? (
          <button
            onClick={startVoiceSession}
            className="btn btn-primary px-8 py-3 text-sm font-semibold rounded-full shadow-[0_0_20px_rgba(56,189,248,0.4)] flex items-center gap-2"
          >
            <Mic size={16} />
            <span>Connect Voice Core</span>
          </button>
        ) : state === 'listening' || state === 'speaking' ? (
          <>
            <button
              onClick={toggleMute}
              className={'p-3.5 rounded-full border transition-colors ' + (isMuted ? 'bg-red-500/20 text-red-400 border-red-500/40' : 'bg-[#101820] text-gray-300 border-[#1E293B] hover:text-[#38BDF8]')}
              title={isMuted ? 'Unmute' : 'Mute'}
            >
              {isMuted ? <MicOff size={20} /> : <Mic size={20} />}
            </button>
            <button
              onClick={endSession}
              className="btn btn-danger px-6 py-3 rounded-full text-xs font-bold flex items-center gap-2 shadow-lg shadow-red-500/20"
            >
              <PhoneOff size={16} />
              <span>Disconnect</span>
            </button>
          </>
        ) : (
          <button
            onClick={() => {
              setState('idle');
              setTranscript('');
            }}
            className="btn btn-secondary px-6 py-2.5 text-xs font-semibold rounded-full"
          >
            Reset Connection
          </button>
        )}
      </div>
    </div>
  );
}
