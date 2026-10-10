import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Mic,
  MicOff,
  PhoneOff,
  AlertCircle,
  Loader2,
  Volume2,
  Sparkles,
  Radio,
  Volume1,
} from 'lucide-react';
import { Room, RoomEvent, Track } from 'livekit-client';
import { getVoiceToken } from '../../services/voiceService';
import toast from 'react-hot-toast';

export default function VoiceAssistant({ onClose }) {
  // Voice states: 'idle' | 'connecting' | 'listening' | 'speaking' | 'unavailable' | 'error'
  const [state, setState] = useState('idle');
  const [isMuted, setIsMuted] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [transcript, setTranscript] = useState('');
  // audioBlocked: true when browser autoplay policy blocks audio output
  const [audioBlocked, setAudioBlocked] = useState(false);

  const roomRef = useRef(null);
  const audioElementsRef = useRef(new Map());

  // Monotonic session counter to guard callbacks against stale execution
  const sessionIdRef = useRef(0);

  // ─── Full cleanup of one Room instance ───────────────────────────────────
  const cleanupRoom = useCallback(async (room, audioElements, sid) => {
    if (!room) {
      console.log(`[VOICE DEBUG] SESSION=${sid} CLEANUP_COMPLETE (no room instance)`);
      return;
    }

    const roomStateBefore = room.state || 'unknown';
    const localTracksBefore = room.localParticipant?.trackPublications?.size || 0;
    const remoteTracksBefore = audioElements?.size || 0;

    console.log(`[VOICE DEBUG] SESSION=${sid} ROOM_STATE_BEFORE=${roomStateBefore}`);
    console.log(`[VOICE DEBUG] SESSION=${sid} LOCAL_TRACKS_BEFORE=${localTracksBefore}`);
    console.log(`[VOICE DEBUG] SESSION=${sid} REMOTE_TRACKS_BEFORE=${remoteTracksBefore}`);

    // Unpublish and stop all local tracks
    if (room.localParticipant) {
      try {
        room.localParticipant.trackPublications.forEach((pub) => {
          if (pub.track) {
            try {
              pub.track.stop();
            } catch (_) {}
          }
        });
      } catch (_) {}
    }

    // 1. Remove all listeners from this specific room instance
    room.removeAllListeners();
    console.log(`[VOICE DEBUG] SESSION=${sid} LISTENERS_CLEANED`);

    // 2. Detach and remove every remote audio element attached for this session
    if (audioElements) {
      audioElements.forEach((el, trackSid) => {
        try {
          if (el && el.parentNode) el.parentNode.removeChild(el);
          el.src = '';
        } catch (_) {}
      });
      audioElements.clear();
    }

    // 3. Disconnect room with stopTracks=true
    try {
      if (room.state !== 'disconnected') {
        await room.disconnect(true);
      }
    } catch (e) {
      console.warn('[VOICE] room.disconnect error:', e);
    }

    console.log(`[VOICE DEBUG] SESSION=${sid} ROOM_DISCONNECTED`);
    console.log(`[VOICE DEBUG] SESSION=${sid} CLEANUP_COMPLETE`);
  }, []);

  // ─── Component unmount: tear down whatever room is active ────────────────
  useEffect(() => {
    return () => {
      const curSid = sessionIdRef.current;
      const room = roomRef.current;
      const audioEls = new Map(audioElementsRef.current);
      roomRef.current = null;
      audioElementsRef.current.clear();
      cleanupRoom(room, audioEls, curSid);
    };
  }, [cleanupRoom]);

  // ─── Resume audio after user taps "Tap to Enable Audio" button ───────────
  const handleResumeAudio = useCallback(async () => {
    if (!roomRef.current) return;
    try {
      await roomRef.current.startAudio();
      setAudioBlocked(false);
      toast.success('Audio playback enabled');
      console.log(`[VOICE DEBUG] SESSION=${sessionIdRef.current} AUDIO_RESUMED via user gesture`);
    } catch (e) {
      console.warn('[VOICE] startAudio failed during resume:', e);
    }
  }, []);

  // ─── CONNECT ─────────────────────────────────────────────────────────────
  const startVoiceSession = async () => {
    const mySessionId = ++sessionIdRef.current;

    console.log(`[VOICE DEBUG] SESSION=${mySessionId} CONNECT_START`);
    setState('connecting');
    setErrorMessage('');
    setAudioBlocked(false);
    setIsMuted(false);
    setTranscript('Initializing encrypted LiveKit WebRTC channel...');

    // ── 0. Tear down any previous room FIRST ──────────────────────────────
    const prevRoom = roomRef.current;
    const prevAudioEls = new Map(audioElementsRef.current);
    roomRef.current = null;
    audioElementsRef.current.clear();
    if (prevRoom) {
      console.log(`[VOICE DEBUG] SESSION=${mySessionId - 1} DISCONNECT_START (auto-cleanup)`);
      await cleanupRoom(prevRoom, prevAudioEls, mySessionId - 1);
    }

    // Guard if session changed during cleanup
    if (sessionIdRef.current !== mySessionId) {
      console.warn(`[VOICE DEBUG] SESSION=${mySessionId} Stale session — aborting after cleanup`);
      return;
    }

    try {
      // ── 1. Fetch fresh token ───────────────────────────────────────────
      const data = await getVoiceToken();
      if (!data || !data.token) {
        throw new Error('Invalid token response from voice service');
      }
      console.log(`[VOICE DEBUG] SESSION=${mySessionId} TOKEN_RECEIVED room=${data.room}`);

      if (sessionIdRef.current !== mySessionId) {
        console.warn(`[VOICE DEBUG] SESSION=${mySessionId} Stale session — aborting after token fetch`);
        return;
      }

      // ── 2. Create fresh Room instance ──────────────────────────────────
      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
        webAudioMix: false,
        audioCaptureDefaults: {
          autoGainControl: true,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      const myAudioEls = audioElementsRef.current;
      roomRef.current = room;

      console.log(`[VOICE DEBUG] SESSION=${mySessionId} ROOM_CREATED`);

      // ── 3. Attach event listeners BEFORE connect() ─────────────────────
      room.on(RoomEvent.Connected, async () => {
        if (sessionIdRef.current !== mySessionId) return;

        console.log(`[VOICE DEBUG] SESSION=${mySessionId} ROOM_CONNECTED`);
        console.log(
          `[VOICE] room.name=${room.name} room.state=${room.state} localParticipant.identity=${room.localParticipant?.identity} remote_participants=${room.remoteParticipants?.size || 0}`
        );

        setState('listening');
        setTranscript('Connected to Nova AI Core. Listening for your command...');
        toast.success('LiveKit Voice Room Connected');

        // Check if agent is already present in room
        room.remoteParticipants.forEach((p) => {
          console.log(
            `[VOICE DEBUG] SESSION=${mySessionId} AGENT_CONNECTED identity=${p.identity} name=${p.name || 'Nova'}`
          );
        });

        try {
          await room.startAudio();
          console.log(`[VOICE DEBUG] SESSION=${mySessionId} AUDIO_STARTED`);
          const audioCtxState = room.canPlaybackAudio ? 'running' : 'suspended';
          console.log(`[VOICE DEBUG] SESSION=${mySessionId} AUDIO_CONTEXT=${audioCtxState}`);
        } catch (e) {
          console.warn('[VOICE] startAudio() initially blocked:', e);
        }
      });

      room.on(RoomEvent.AudioPlaybackStatusChanged, (canPlay) => {
        if (sessionIdRef.current !== mySessionId) return;
        console.log(`[VOICE DEBUG] SESSION=${mySessionId} AUDIO_PLAYBACK_STATUS canPlay=${canPlay}`);
        setAudioBlocked(!canPlay);
      });

      room.on(RoomEvent.ParticipantConnected, (participant) => {
        if (sessionIdRef.current !== mySessionId) return;
        console.log(
          `[VOICE DEBUG] SESSION=${mySessionId} AGENT_CONNECTED identity=${participant.identity} name=${participant.name || 'Nova'}`
        );
      });

      room.on(RoomEvent.TrackSubscribed, async (track, publication, participant) => {
        if (sessionIdRef.current !== mySessionId) return;
        console.log(
          `[VOICE DEBUG] SESSION=${mySessionId} TRACK_SUBSCRIBED kind=${track.kind} sid=${publication.trackSid} from=${participant.identity}`
        );

        if (track.kind !== Track.Kind.Audio) return;

        const element = track.attach();
        element.autoplay = true;
        document.body.appendChild(element);
        myAudioEls.set(publication.trackSid, element);

        console.log(
          `[VOICE DEBUG] SESSION=${mySessionId} AUDIO_ATTACHED muted=${element.muted} volume=${element.volume} sid=${publication.trackSid}`
        );

        try {
          await element.play();
          console.log(`[VOICE DEBUG] SESSION=${mySessionId} AUDIO_PLAY_RESULT=success`);
        } catch (playErr) {
          console.warn(`[VOICE DEBUG] SESSION=${mySessionId} AUDIO_PLAY_RESULT=blocked:`, playErr.message);
          if (sessionIdRef.current === mySessionId) {
            setAudioBlocked(true);
          }
        }

        setState('speaking');
      });

      room.on(RoomEvent.TrackUnsubscribed, (track, publication) => {
        if (sessionIdRef.current !== mySessionId) return;
        console.log(`[VOICE DEBUG] SESSION=${mySessionId} TRACK_UNSUBSCRIBED sid=${publication.trackSid}`);
        const el = myAudioEls.get(publication.trackSid);
        if (el) {
          try {
            track.detach(el);
          } catch (_) {}
          if (el.parentNode) el.parentNode.removeChild(el);
          el.src = '';
          myAudioEls.delete(publication.trackSid);
        }
        setState('listening');
      });

      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        if (sessionIdRef.current !== mySessionId) return;
        if (speakers.length > 0) {
          const isAgent = speakers.some((s) => !s.isLocal);
          setState(isAgent ? 'speaking' : 'listening');
        }
      });

      room.on(RoomEvent.Disconnected, () => {
        console.log(
          `[VOICE DEBUG] SESSION=${mySessionId} ROOM_DISCONNECTED_EVENT isStale=${sessionIdRef.current !== mySessionId}`
        );
        if (sessionIdRef.current !== mySessionId) return;
        setState('idle');
        setTranscript('');
        setAudioBlocked(false);
      });

      // ── 4. Connect ────────────────────────────────────────────────────
      await room.connect(data.url, data.token);

      if (sessionIdRef.current !== mySessionId) {
        console.warn(`[VOICE DEBUG] SESSION=${mySessionId} Stale session after connect — disconnecting`);
        room.removeAllListeners();
        room.disconnect(true);
        return;
      }

      // ── 5. Verify microphone device and publish track ─────────────────
      try {
        if (navigator?.mediaDevices?.getUserMedia) {
          try {
            const testStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const testTrack = testStream.getAudioTracks()[0];
            if (testTrack) {
              console.log(
                `[VOICE DEBUG] SESSION=${mySessionId} MEDIA_STREAM_TRACK readyState=${testTrack.readyState} enabled=${testTrack.enabled} muted=${testTrack.muted}`
              );
              testTrack.stop();
            }
          } catch (gumErr) {
            console.warn(`[VOICE DEBUG] SESSION=${mySessionId} getUserMedia probe warning:`, gumErr);
          }
        }

        await room.localParticipant.setMicrophoneEnabled(true);
        console.log(`[VOICE DEBUG] SESSION=${mySessionId} MIC_ENABLED`);

        const pubs = [...room.localParticipant.audioTrackPublications.values()];
        console.log(`[VOICE DEBUG] SESSION=${mySessionId} MIC_PUBLICATIONS=${pubs.length}`);
        pubs.forEach((pub) => {
          console.log(`[VOICE] local mic publication sid=${pub.trackSid} muted=${pub.isMuted}`);
        });
      } catch (micErr) {
        console.warn(`[VOICE DEBUG] SESSION=${mySessionId} Microphone error:`, micErr);
        toast.error('Microphone permission required for voice');
        setErrorMessage('Microphone access denied or unavailable in this browser.');
        setState('error');
        if (sessionIdRef.current === mySessionId) {
          roomRef.current = null;
          audioElementsRef.current.clear();
        }
        room.removeAllListeners();
        room.disconnect(true);
        return;
      }

      setState('listening');
    } catch (err) {
      if (sessionIdRef.current !== mySessionId) return;
      console.error(`[VOICE DEBUG] SESSION=${mySessionId} LiveKit error:`, err);
      if (err.response && err.response.status === 503) {
        setState('unavailable');
        setErrorMessage('Voice interface is not configured on this server.');
      } else {
        setState('error');
        setErrorMessage(err.message || 'Could not establish LiveKit voice session.');
      }
    }
  };

  // ─── MUTE TOGGLE ─────────────────────────────────────────────────────────
  const toggleMute = async () => {
    if (!roomRef.current || !roomRef.current.localParticipant) return;
    const newMuteState = !isMuted;
    await roomRef.current.localParticipant.setMicrophoneEnabled(!newMuteState);
    setIsMuted(newMuteState);
    toast(newMuteState ? 'Microphone muted' : 'Microphone active');
  };

  // ─── DISCONNECT ───────────────────────────────────────────────────────────
  const endSession = async () => {
    const curSid = sessionIdRef.current;
    console.log(`[VOICE DEBUG] SESSION=${curSid} DISCONNECT_START`);

    sessionIdRef.current++;

    const room = roomRef.current;
    const audioEls = new Map(audioElementsRef.current);
    roomRef.current = null;
    audioElementsRef.current.clear();

    setState('idle');
    setTranscript('');
    setAudioBlocked(false);
    setIsMuted(false);

    await cleanupRoom(room, audioEls, curSid);

    if (onClose) onClose();
  };

  // ─── UI helpers ───────────────────────────────────────────────────────────
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
        <span>AI VOICE</span>
        <span className={'text-[10px] px-2 py-0.5 rounded-full uppercase font-bold ' + getPillBadgeClass()}>
          {state === 'listening' ? 'ONLINE' : state === 'speaking' ? 'SPEAKING' : state.toUpperCase()}
        </span>
      </div>

      {/* Audio blocked banner — shown when browser blocks autoplay */}
      {audioBlocked && (state === 'listening' || state === 'speaking') && (
        <button
          onClick={handleResumeAudio}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/40 text-amber-400 text-xs font-semibold hover:bg-amber-500/20 transition"
        >
          <Volume1 size={15} />
          Tap to Enable Audio Playback
        </button>
      )}

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
            : 'Stream real-time low-latency voice audio directly into the platform.'}
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
              setAudioBlocked(false);
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
