/**
 * RideNow — Premium Animated Map Component
 * ==========================================
 * Leaflet + CartoDB dark tiles with custom animated markers.
 *
 * Marker types:
 *   'passenger'  – person avatar with soft glow
 *   'pickup'     – animated pulsing cyan ring
 *   'dropoff'    – glowing emerald destination flag
 *   'driver'     – animated stylized car (rotates by heading)
 *   'nearby'     – small ambient car for nearby drivers
 *   'hotspot'    – demand heatmap zone marker (pulsing amber)
 *   'default'    – simple dot
 *
 * Props:
 *   center         [lat, lng]
 *   markers        [{lat, lng, type, popup, heading?, id?}]
 *   route          [[lat, lng], ...]  – polyline
 *   interactive    boolean
 *   animateDrivers boolean – when true, driver markers glide smoothly
 *                            between position updates (800ms interpolation)
 */

import { useEffect, useRef, useMemo, useState, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Polyline } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// ── Icon factory ──────────────────────────────────────────────────────────────

function createIcon(type, heading = 0) {
  let html = '';

  switch (type) {
    case 'passenger':
      html = `
        <div style="
          position:relative;
          width:40px;height:40px;
          display:flex;align-items:center;justify-content:center;
        ">
          <!-- Outer glow ring -->
          <div style="
            position:absolute;
            width:40px;height:40px;
            border-radius:50%;
            background:rgba(56,189,248,0.12);
            border:1.5px solid rgba(56,189,248,0.35);
            animation:pickup-pulse 2.5s ease-out infinite;
          "></div>
          <!-- Avatar circle -->
          <div style="
            width:28px;height:28px;
            border-radius:50%;
            background:linear-gradient(135deg,#0D141B 0%,#1E293B 100%);
            border:2px solid #38BDF8;
            display:flex;align-items:center;justify-content:center;
            box-shadow:0 0 12px rgba(56,189,248,0.45);
          ">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#38BDF8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="8" r="4"/>
              <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
            </svg>
          </div>
        </div>`;
      break;

    case 'pickup':
      html = `
        <div style="position:relative;width:36px;height:44px;">
          <!-- Pin body -->
          <div style="
            width:36px;height:36px;
            border-radius:50% 50% 50% 0;
            transform:rotate(-45deg);
            background:linear-gradient(135deg,#38BDF8 0%,#0EA5E9 100%);
            border:2.5px solid #F5F7FA;
            box-shadow:0 0 18px rgba(56,189,248,0.6);
            display:flex;align-items:center;justify-content:center;
            animation:pickup-glow 2s ease-in-out infinite;
          ">
            <div style="transform:rotate(45deg)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#05070A" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="4"/>
              </svg>
            </div>
          </div>
          <!-- Pulse ring -->
          <div style="
            position:absolute;top:-4px;left:-4px;
            width:44px;height:44px;
            border-radius:50%;
            border:2px solid rgba(56,189,248,0.4);
            animation:pickup-pulse 2s ease-out infinite;
          "></div>
        </div>`;
      break;

    case 'dropoff':
      html = `
        <div style="position:relative;width:36px;height:44px;">
          <!-- Pin body -->
          <div style="
            width:36px;height:36px;
            border-radius:50% 50% 50% 0;
            transform:rotate(-45deg);
            background:linear-gradient(135deg,#10B981 0%,#059669 100%);
            border:2.5px solid #F5F7FA;
            box-shadow:0 0 18px rgba(16,185,129,0.6);
            display:flex;align-items:center;justify-content:center;
            animation:destination-glow 2.5s ease-in-out infinite;
          ">
            <div style="transform:rotate(45deg)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#05070A" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
              </svg>
            </div>
          </div>
        </div>`;
      break;

    case 'driver': {
      const rot = heading || 0;
      html = `
        <div style="
          position:relative;
          width:52px;height:52px;
          display:flex;align-items:center;justify-content:center;
          animation:driver-float 3s ease-in-out infinite;
        ">
          <!-- Outer glow -->
          <div style="
            position:absolute;
            width:52px;height:52px;
            border-radius:50%;
            background:rgba(56,189,248,0.1);
            border:1.5px solid rgba(56,189,248,0.3);
          "></div>
          <!-- Car SVG rotated by heading -->
          <div style="transform:rotate(${rot}deg);width:38px;height:22px;">
            <svg width="38" height="22" viewBox="0 0 80 36" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="8" y="18" width="64" height="14" rx="4" fill="#0E1E2A"/>
              <path d="M18 18 L22 8 Q23 6 25 6 L55 6 Q57 6 58 8 L62 18 Z" fill="#132130"/>
              <path d="M25 8 L23 17 L40 17 L40 8 Z" fill="#38BDF8" opacity="0.55"/>
              <path d="M42 8 L42 17 L57 17 L55 8 Z" fill="#38BDF8" opacity="0.55"/>
              <line x1="40" y1="7" x2="40" y2="17" stroke="#0E1E2A" stroke-width="1.5"/>
              <rect x="68" y="21" width="8" height="4" rx="2" fill="#38BDF8" opacity="0.9"/>
              <rect x="4" y="21" width="6" height="4" rx="2" fill="#EF4444" opacity="0.8"/>
              <circle cx="20" cy="32" r="5" fill="#0A1420" stroke="#1E3A4A" stroke-width="1.5"/>
              <circle cx="20" cy="32" r="2.5" fill="#1E3A4A"/>
              <circle cx="60" cy="32" r="5" fill="#0A1420" stroke="#1E3A4A" stroke-width="1.5"/>
              <circle cx="60" cy="32" r="2.5" fill="#1E3A4A"/>
              <circle cx="40" cy="14" r="3.5" fill="#38BDF8" opacity="0.9"/>
              <circle cx="40" cy="14" r="2" fill="#05070A"/>
            </svg>
          </div>
        </div>`;
      break;
    }

    case 'nearby': {
      html = `
        <div style="
          width:28px;height:20px;
          animation:nearby-appear 0.4s ease-out both;
          opacity:0.75;
        ">
          <svg width="28" height="20" viewBox="0 0 80 36" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="8" y="18" width="64" height="14" rx="4" fill="#0E1E2A"/>
            <path d="M18 18 L22 8 Q23 6 25 6 L55 6 Q57 6 58 8 L62 18 Z" fill="#132130"/>
            <path d="M25 8 L23 17 L40 17 L40 8 Z" fill="#38BDF8" opacity="0.4"/>
            <path d="M42 8 L42 17 L57 17 L55 8 Z" fill="#38BDF8" opacity="0.4"/>
            <rect x="68" y="21" width="8" height="4" rx="2" fill="#38BDF8" opacity="0.7"/>
            <circle cx="20" cy="32" r="5" fill="#0A1420" stroke="#1E3A4A" stroke-width="1.5"/>
            <circle cx="60" cy="32" r="5" fill="#0A1420" stroke="#1E3A4A" stroke-width="1.5"/>
          </svg>
        </div>`;
      break;
    }

    case 'hotspot': {
      html = `
        <div style="position:relative;width:44px;height:44px;display:flex;align-items:center;justify-content:center;">
          <!-- Outer pulse ring -->
          <div style="
            position:absolute;
            width:44px;height:44px;
            border-radius:50%;
            border:2px solid rgba(251,146,60,0.35);
            animation:pickup-pulse 2s ease-out infinite;
          "></div>
          <!-- Middle ring -->
          <div style="
            position:absolute;
            width:32px;height:32px;
            border-radius:50%;
            background:rgba(251,146,60,0.08);
            border:1.5px solid rgba(251,146,60,0.45);
            animation:pickup-pulse 2s ease-out infinite 0.5s;
          "></div>
          <!-- Core dot -->
          <div style="
            width:16px;height:16px;
            border-radius:50%;
            background:linear-gradient(135deg,#FB923C 0%,#F97316 100%);
            border:2px solid #FED7AA;
            box-shadow:0 0 12px rgba(251,146,60,0.6);
            display:flex;align-items:center;justify-content:center;
          ">
            <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="#7C2D12" stroke-width="3">
              <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
              <polyline points="17 6 23 6 23 12"/>
            </svg>
          </div>
        </div>`;
      break;
    }

    default:
      html = `<div style="width:10px;height:10px;border-radius:50%;background:#38BDF8;box-shadow:0 0 8px #38BDF8;border:2px solid #F5F7FA;"></div>`;
  }

  const sizes = {
    passenger: [40, 40],
    pickup:    [36, 44],
    dropoff:   [36, 44],
    driver:    [52, 52],
    nearby:    [28, 20],
    hotspot:   [44, 44],
    default:   [10, 10],
  };

  const anchors = {
    passenger: [20, 20],
    pickup:    [18, 36],
    dropoff:   [18, 36],
    driver:    [26, 26],
    nearby:    [14, 10],
    hotspot:   [22, 22],
    default:   [5, 5],
  };

  const sz = sizes[type] || sizes.default;
  const an = anchors[type] || anchors.default;

  return L.divIcon({
    html,
    className: 'custom-leaflet-icon',
    iconSize: sz,
    iconAnchor: an,
    popupAnchor: [0, -an[1]],
  });
}

// ── Smooth animated marker hook ────────────────────────────────────────────────
// Interpolates marker positions using requestAnimationFrame for butter-smooth
// driver movement. Only applies to markers where type === 'driver'.

function lerp(a, b, t) { return a + (b - a) * t; }

function lerpAngle(a, b, t) {
  // Shortest-arc interpolation for heading (degrees)
  let diff = ((b - a + 540) % 360) - 180;
  return a + diff * t;
}

/**
 * useAnimatedMarkers — returns a display copy of markers where
 * driver-type markers smoothly transition between their position updates.
 *
 * Rules of Hooks: all hooks unconditionally called; animation logic
 * is controlled by the `animateDrivers` flag *inside* effects.
 */
function useAnimatedMarkers(markers, animateDrivers, durationMs = 800) {
  const [displayMarkers, setDisplayMarkers] = useState(markers);
  const prevRef = useRef({});   // { markerId: { lat, lng, heading } }
  const rafRef  = useRef({});   // { markerId: rafId }

  useEffect(() => {
    // When animation is off, just mirror incoming markers directly
    if (!animateDrivers) {
      setDisplayMarkers(markers);
      return;
    }

    const now = performance.now();

    setDisplayMarkers(prev => {
      const next = markers.map(m => {
        if (m.type !== 'driver' && m.type !== 'nearby') return m;
        const id = m.id ?? `${m.lat}-${m.lng}-${m.type}`;
        const prevPos = prevRef.current[id];
        if (!prevPos) {
          // First render — no animation needed, just record position
          prevRef.current[id] = { lat: m.lat, lng: m.lng, heading: m.heading || 0 };
          return m;
        }
        // Kick off interpolation from previous → new position
        const startLat  = prevPos.lat;
        const startLng  = prevPos.lng;
        const startHead = prevPos.heading || 0;
        const endLat    = m.lat;
        const endLng    = m.lng;
        const endHead   = m.heading || 0;
        const startTime = now;

        if (rafRef.current[id]) cancelAnimationFrame(rafRef.current[id]);

        const step = (timestamp) => {
          const elapsed = timestamp - startTime;
          const t = Math.min(elapsed / durationMs, 1);
          const eased = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; // ease-in-out

          const iLat  = lerp(startLat,  endLat,  eased);
          const iLng  = lerp(startLng,  endLng,  eased);
          const iHead = lerpAngle(startHead, endHead, eased);

          setDisplayMarkers(dm =>
            dm.map(dm_m => {
              const dm_id = dm_m.id ?? `${dm_m.lat}-${dm_m.lng}-${dm_m.type}`;
              return dm_id === id
                ? { ...dm_m, lat: iLat, lng: iLng, heading: iHead }
                : dm_m;
            })
          );

          if (t < 1) {
            rafRef.current[id] = requestAnimationFrame(step);
          } else {
            prevRef.current[id] = { lat: endLat, lng: endLng, heading: endHead };
          }
        };

        rafRef.current[id] = requestAnimationFrame(step);
        // Return the marker at its *start* position so first frame is stable
        return { ...m, lat: startLat, lng: startLng, heading: startHead };
      });
      return next;
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [markers, animateDrivers]);

  // Cleanup all RAF loops on unmount to prevent memory leaks
  useEffect(() => {
    return () => {
      Object.values(rafRef.current).forEach(rafId => cancelAnimationFrame(rafId));
    };
  }, []);

  return displayMarkers;
}


// ── Map bounds auto-fit ────────────────────────────────────────────────────

function MapFitBounds({ markers, route }) {
  const map = useMap();

  useEffect(() => {
    if (route && route.length > 1) {
      const bounds = L.latLngBounds(route);
      map.fitBounds(bounds, { padding: [56, 56], maxZoom: 15, animate: true });
    } else if (markers && markers.length > 0) {
      const validMarkers = markers.filter(m => m.lat && m.lng);
      if (validMarkers.length === 0) return;
      if (validMarkers.length === 1) {
        map.setView([validMarkers[0].lat, validMarkers[0].lng], 14, { animate: true });
      } else {
        const bounds = L.latLngBounds(validMarkers.map(m => [m.lat, m.lng]));
        map.fitBounds(bounds, { padding: [56, 56], maxZoom: 15, animate: true });
      }
    }
  }, [markers, route, map]);

  return null;
}

// ── Main Map component ────────────────────────────────────────────────────

const DEFAULT_CENTER = [12.9716, 77.5946]; // Bengaluru

const Map = ({
  center = DEFAULT_CENTER,
  markers = [],
  route = [],
  interactive = true,
  animateDrivers = false,
  className = '',
}) => {
  // CartoDB Dark Matter for premium command-center look
  const tileUrl = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';

  // Apply smooth animation to driver markers when enabled
  const displayMarkers = useAnimatedMarkers(markers, animateDrivers);

  // Build icon instances (memoized per unique type+heading combo)
  const iconInstances = useMemo(() => {
    const cache = {};
    displayMarkers.forEach(m => {
      const key = `${m.type}-${Math.round(m.heading || 0)}`;
      if (!cache[key]) {
        cache[key] = createIcon(m.type || 'default', m.heading);
      }
    });
    return cache;
  }, [displayMarkers]);

  return (
    <div
      className={`w-full h-full min-h-[250px] rounded-2xl overflow-hidden z-0 isolate border border-[#1E293B] ${className}`}
    >
      <MapContainer
        center={center}
        zoom={13}
        scrollWheelZoom={interactive}
        dragging={interactive}
        zoomControl={interactive}
        doubleClickZoom={interactive}
        touchZoom={interactive}
        keyboard={interactive}
        className="w-full h-full"
        attributionControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          url={tileUrl}
          maxZoom={19}
        />

        {/* Animated route polyline */}
        {route && route.length > 1 && (
          <>
            {/* Base route — subtle glow */}
            <Polyline
              positions={route}
              pathOptions={{
                color: 'rgba(56,189,248,0.15)',
                weight: 10,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            />
            {/* Main route line */}
            <Polyline
              positions={route}
              pathOptions={{
                color: '#38BDF8',
                weight: 3.5,
                opacity: 0.9,
                lineCap: 'round',
                lineJoin: 'round',
                dashArray: '0',
              }}
            />
            {/* Animated flow dashes */}
            <Polyline
              positions={route}
              pathOptions={{
                color: '#7DD3FC',
                weight: 2,
                opacity: 0.7,
                lineCap: 'round',
                dashArray: '12 10',
                className: 'route-animated',
              }}
            />
          </>
        )}

        {/* Markers */}
        {displayMarkers.map((marker, idx) => {
          if (!marker.lat || !marker.lng) return null;
          const key = `${marker.type}-${Math.round(marker.heading || 0)}`;
          const icon = iconInstances[key] || createIcon('default');
          return (
            <Marker
              key={`${marker.id ?? idx}-${marker.type}`}
              position={[marker.lat, marker.lng]}
              icon={icon}
            >
              {marker.popup && (
                <Popup
                  className="font-sans"
                  closeButton={false}
                >
                  <div
                    style={{
                      background: '#101820',
                      border: '1px solid #1E293B',
                      borderRadius: '10px',
                      padding: '8px 12px',
                      color: '#F5F7FA',
                      fontSize: '13px',
                      fontWeight: 500,
                      minWidth: '120px',
                    }}
                  >
                    {marker.popup}
                  </div>
                </Popup>
              )}
            </Marker>
          );
        })}

        <MapFitBounds markers={displayMarkers} route={route} />
      </MapContainer>
    </div>
  );
};

export default Map;
