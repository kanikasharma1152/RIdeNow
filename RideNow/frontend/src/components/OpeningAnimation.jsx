/**
 * RideNow — Opening Cinematic Boot Animation
 * ============================================
 * Plays on EVERY full page load / browser refresh — it is the global
 * RideNow boot experience, not a one-time intro.
 *
 * Respects prefers-reduced-motion (skips instantly).
 * Skip button appears after 600ms.
 *
 * NOTE: Authentication state (JWT in localStorage['token']) is completely
 * separate and is never touched here. Only the visual animation is
 * controlled by this component.
 */

import { useEffect, useRef, useState, useCallback } from 'react';

// Check reduced motion preference once at module level.
// If the user prefers reduced motion we skip the animation immediately.
const prefersReducedMotion =
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export default function OpeningAnimation({ onComplete }) {
  // Animation always plays on every boot unless reduced-motion is preferred.
  // No localStorage "seen" check — this is intentional (global boot animation).
  const [done, setDone] = useState(prefersReducedMotion);
  const [phase, setPhase] = useState('road'); // road → car → logo → online → exit
  const [showSkip, setShowSkip] = useState(false);
  const timerRefs = useRef([]);

  const finish = useCallback(() => {
    // Cancel all pending timers
    timerRefs.current.forEach(clearTimeout);
    // NOTE: No localStorage.setItem here — we intentionally do NOT persist
    // the "seen" state so the animation plays on every page load.
    setPhase('exit');
    // Short exit fade, then unmount
    const t = setTimeout(() => {
      setDone(true);
      onComplete?.();
    }, 400);
    timerRefs.current.push(t);
  }, [onComplete]);

  useEffect(() => {
    if (done) {
      onComplete?.();
      return;
    }

    const t = [];

    // Show skip button after 600ms
    t.push(setTimeout(() => setShowSkip(true), 600));

    // Phase timeline
    t.push(setTimeout(() => setPhase('car'),    500));   // road visible → car enters
    t.push(setTimeout(() => setPhase('logo'),   1200));  // car settled → logo
    t.push(setTimeout(() => setPhase('online'), 1700));  // logo → AI ONLINE
    t.push(setTimeout(() => finish(),           2400));  // exit

    timerRefs.current = t;
    return () => t.forEach(clearTimeout);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (done) return null;

  return (
    <div
      className="fixed inset-0 z-[9999] flex flex-col items-center justify-center overflow-hidden select-none"
      style={{
        background: 'linear-gradient(135deg, #05070A 0%, #080E15 50%, #05070A 100%)',
        animation: phase === 'exit' ? 'fade-out-up 0.4s ease-in forwards' : undefined,
      }}
      aria-label="RideNow loading"
      role="status"
    >
      {/* ── Background city grid ─────────────────────────────────── */}
      <CityGrid />

      {/* ── Main stage ───────────────────────────────────────────── */}
      <div className="relative flex flex-col items-center gap-8 px-8">

        {/* Road SVG + Car */}
        <div className="relative w-72 sm:w-96 h-20 flex items-end justify-center">
          <RoadSVG phase={phase} />
          <CarSVG phase={phase} />
        </div>

        {/* Logo block */}
        <div
          style={{
            opacity: phase === 'logo' || phase === 'online' ? 1 : 0,
            transform: phase === 'logo' || phase === 'online' ? 'translateY(0) scale(1)' : 'translateY(10px) scale(0.95)',
            transition: 'opacity 0.45s ease-out, transform 0.45s ease-out',
          }}
          className="flex flex-col items-center gap-3"
        >
          {/* Logo mark */}
          <div className="flex items-center gap-3">
            <LogoMark />
            <span
              className="text-3xl sm:text-4xl font-bold tracking-tight text-[#F5F7FA]"
              style={{ letterSpacing: '-0.02em' }}
            >
              Ride<span className="text-[#38BDF8]">Now</span>
            </span>
          </div>

          {/* AI Online indicator */}
          <div
            style={{
              opacity: phase === 'online' ? 1 : 0,
              transform: phase === 'online' ? 'translateY(0)' : 'translateY(4px)',
              transition: 'opacity 0.3s ease-out 0.1s, transform 0.3s ease-out 0.1s',
            }}
            className="flex items-center gap-2 px-4 py-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10"
          >
            <span
              className="w-2 h-2 rounded-full bg-emerald-400"
              style={{ animation: 'ai-online-blink 1s ease-in-out infinite' }}
            />
            <span className="text-xs font-semibold text-emerald-400 tracking-widest uppercase">
              AI Online
            </span>
          </div>
        </div>
      </div>

      {/* Skip button */}
      {showSkip && (
        <button
          onClick={finish}
          className="absolute bottom-10 right-8 text-xs text-gray-500 hover:text-gray-300 transition-colors px-3 py-1.5 rounded-lg border border-gray-700/50 hover:border-gray-500/50"
          style={{ animation: 'screen-reveal 0.3s ease-out both' }}
        >
          Skip
        </button>
      )}
    </div>
  );
}

/* ── Sub-components ─────────────────────────────────────────────────────── */

function CityGrid() {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden">
      {/* Horizontal scan lines — subtle city grid */}
      <svg
        className="absolute inset-0 w-full h-full opacity-[0.035]"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <pattern id="grid" x="0" y="0" width="60" height="60" patternUnits="userSpaceOnUse">
            <path d="M 60 0 L 0 0 0 60" fill="none" stroke="#38BDF8" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />
      </svg>

      {/* Radial glow center */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 60% 50% at 50% 50%, rgba(56,189,248,0.06) 0%, transparent 70%)',
        }}
      />

      {/* Top cityline silhouette */}
      <svg
        className="absolute top-0 left-0 w-full opacity-[0.12]"
        height="120"
        viewBox="0 0 1200 120"
        preserveAspectRatio="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M0,120 L0,80 L40,80 L40,40 L60,40 L60,55 L80,55 L80,20 L100,20 L100,55 L120,55 L120,60 L150,60 L150,35 L170,35 L170,60 L200,60 L200,45 L230,45 L230,70 L260,70 L260,30 L280,30 L280,70 L310,70 L310,50 L340,50 L340,75 L370,75 L370,40 L400,40 L400,75 L430,75 L430,55 L460,55 L460,80 L490,80 L490,45 L520,45 L520,80 L550,80 L550,60 L580,60 L580,35 L610,35 L610,60 L640,60 L640,50 L670,50 L670,75 L700,75 L700,40 L730,40 L730,75 L760,75 L760,55 L790,55 L790,80 L820,80 L820,45 L850,45 L850,80 L880,80 L880,60 L910,60 L910,30 L940,30 L940,60 L970,60 L970,50 L1000,50 L1000,75 L1030,75 L1030,40 L1060,40 L1060,75 L1090,75 L1090,55 L1120,55 L1120,80 L1150,80 L1150,60 L1180,60 L1180,80 L1200,80 L1200,120 Z"
          fill="#38BDF8"
        />
      </svg>
    </div>
  );
}

function RoadSVG({ phase }) {
  const visible = phase !== 'road' ? 1 : 0;
  return (
    <svg
      viewBox="0 0 384 48"
      className="absolute bottom-0 left-0 w-full"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Road surface */}
      <rect
        x="0" y="28" width="384" height="20"
        rx="4"
        fill="#0D1A24"
        style={{
          opacity: visible,
          transition: 'opacity 0.4s ease-out',
        }}
      />
      {/* Road edge lines */}
      <line
        x1="0" y1="28" x2="384" y2="28"
        stroke="#1E3A4A" strokeWidth="1.5"
        style={{ opacity: visible, transition: 'opacity 0.4s ease-out' }}
      />
      <line
        x1="0" y1="48" x2="384" y2="48"
        stroke="#1E3A4A" strokeWidth="1.5"
        style={{ opacity: visible, transition: 'opacity 0.4s ease-out' }}
      />
      {/* Center dashes — animated */}
      <line
        x1="0" y1="38" x2="384" y2="38"
        stroke="#38BDF8"
        strokeWidth="1.5"
        strokeDasharray="20 16"
        style={{
          opacity: visible ? 0.35 : 0,
          transition: 'opacity 0.5s ease-out',
          animation: visible ? 'route-flow 1.5s linear infinite' : 'none',
        }}
      />
      {/* Main animated road line (draw on entry) */}
      <line
        x1="0" y1="28" x2="384" y2="28"
        stroke="#38BDF8"
        strokeWidth="2"
        strokeDasharray="384"
        style={{
          strokeDashoffset: visible ? 0 : 384,
          transition: visible ? 'stroke-dashoffset 0.6s ease-out' : 'none',
          opacity: 0.7,
        }}
      />
    </svg>
  );
}

function CarSVG({ phase }) {
  const carVisible = phase === 'car' || phase === 'logo' || phase === 'online';
  return (
    <div
      style={{
        position: 'absolute',
        bottom: 20,
        left: '50%',
        transform: carVisible
          ? 'translateX(-50%) translateX(0px)'
          : 'translateX(-50%) translateX(-160px)',
        opacity: carVisible ? 1 : 0,
        transition: carVisible
          ? 'transform 0.75s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.3s ease-out'
          : 'none',
        animation: carVisible ? 'driver-float 3s ease-in-out 1s infinite' : 'none',
        willChange: 'transform',
      }}
    >
      <svg
        width="80"
        height="36"
        viewBox="0 0 80 36"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Car glow */}
        <ellipse cx="40" cy="32" rx="28" ry="4" fill="#38BDF8" opacity="0.18" />
        
        {/* Car body */}
        <rect x="8" y="18" width="64" height="14" rx="4" fill="#0E1E2A" />
        
        {/* Cabin */}
        <path
          d="M18 18 L22 8 Q23 6 25 6 L55 6 Q57 6 58 8 L62 18 Z"
          fill="#132130"
        />
        
        {/* Windows */}
        <path
          d="M25 8 L23 17 L40 17 L40 8 Z"
          fill="#38BDF8"
          opacity="0.55"
        />
        <path
          d="M42 8 L42 17 L57 17 L55 8 Z"
          fill="#38BDF8"
          opacity="0.55"
        />
        
        {/* Window divider */}
        <line x1="40" y1="7" x2="40" y2="17" stroke="#0E1E2A" strokeWidth="1.5" />
        
        {/* Headlights */}
        <rect x="68" y="21" width="8" height="4" rx="2" fill="#38BDF8" opacity="0.95" />
        <ellipse cx="73" cy="23" rx="5" ry="2.5" fill="#38BDF8" opacity="0.25" />
        
        {/* Taillights */}
        <rect x="4" y="21" width="6" height="4" rx="2" fill="#EF4444" opacity="0.85" />
        
        {/* Wheels */}
        <circle cx="20" cy="32" r="5" fill="#0A1420" stroke="#1E3A4A" strokeWidth="1.5" />
        <circle cx="20" cy="32" r="2.5" fill="#1E3A4A" />
        <circle cx="60" cy="32" r="5" fill="#0A1420" stroke="#1E3A4A" strokeWidth="1.5" />
        <circle cx="60" cy="32" r="2.5" fill="#1E3A4A" />
        
        {/* Door line */}
        <line x1="40" y1="18" x2="40" y2="32" stroke="#1E3A4A" strokeWidth="0.75" opacity="0.6" />
        
        {/* Door handle */}
        <rect x="34" y="23" width="5" height="1.5" rx="0.75" fill="#1E3A4A" />
        <rect x="41" y="23" width="5" height="1.5" rx="0.75" fill="#1E3A4A" />
        
        {/* RideNow emblem on car */}
        <circle cx="40" cy="14" r="3.5" fill="#38BDF8" opacity="0.9" />
        <circle cx="40" cy="14" r="2" fill="#05070A" />
      </svg>
    </div>
  );
}

function LogoMark() {
  return (
    <div
      className="w-10 h-10 rounded-xl flex items-center justify-center"
      style={{
        background: 'linear-gradient(135deg, #38BDF8 0%, #0EA5E9 100%)',
        boxShadow: '0 0 20px rgba(56, 189, 248, 0.4)',
      }}
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path
          d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"
          stroke="#05070A"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="7" cy="17" r="2" stroke="#05070A" strokeWidth="2" />
        <path d="M9 17h6" stroke="#05070A" strokeWidth="2" strokeLinecap="round" />
        <circle cx="17" cy="17" r="2" stroke="#05070A" strokeWidth="2" />
      </svg>
    </div>
  );
}
