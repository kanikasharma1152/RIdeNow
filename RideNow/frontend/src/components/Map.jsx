import { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Polyline } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Custom icons using Lucide-like SVG designs
const createCustomIcon = (type) => {
  let html = '';
  if (type === 'pickup') {
    html = `<div class="w-8 h-8 flex items-center justify-center bg-[#38BDF8] text-[#05070A] rounded-full shadow-[0_0_15px_rgba(56,189,248,0.5)] border-2 border-[#F5F7FA]"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg></div>`;
  } else if (type === 'dropoff') {
    html = `<div class="w-8 h-8 flex items-center justify-center bg-[#F5F7FA] text-[#05070A] rounded-full shadow-lg border-2 border-[#38BDF8]"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg></div>`;
  } else if (type === 'driver') {
    html = `<div class="w-10 h-10 flex items-center justify-center bg-[#101820] text-[#38BDF8] rounded-full shadow-[0_0_20px_rgba(56,189,248,0.4)] border-2 border-[#38BDF8] animate-pulse"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/></svg></div>`;
  } else {
    // Default / Current user
    html = `<div class="w-4 h-4 bg-[#38BDF8] rounded-full shadow-[0_0_10px_#38BDF8] border-2 border-[#F5F7FA]"></div>`;
  }

  return L.divIcon({
    html,
    className: 'custom-leaflet-icon',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -16]
  });
};

const iconCache = {
  pickup: createCustomIcon('pickup'),
  dropoff: createCustomIcon('dropoff'),
  driver: createCustomIcon('driver'),
  default: createCustomIcon('default'),
};

// Component to handle dynamic map bounds fitting
const MapFitBounds = ({ markers, route }) => {
  const map = useMap();
  
  useEffect(() => {
    if (route && route.length > 0) {
      const bounds = L.latLngBounds(route);
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    } else if (markers && markers.length > 0) {
      const bounds = L.latLngBounds(markers.map(m => [m.lat, m.lng]));
      if (markers.length === 1) {
        map.setView([markers[0].lat, markers[0].lng], 14);
      } else {
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
      }
    }
  }, [markers, route, map]);
  
  return null;
};

// interactive flag allows disabling drag/zoom for preview maps
const Map = ({ center = [12.9716, 77.5946], markers = [], route = [], interactive = true }) => {
  // Dark Matter tiles from CartoDB for command-center look
  const tileUrl = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
  
  return (
    <div className="w-full h-full min-h-[250px] rounded-2xl overflow-hidden z-0 isolate border border-[#1E293B]">
      <MapContainer 
        center={center} 
        zoom={13} 
        scrollWheelZoom={interactive}
        dragging={interactive}
        zoomControl={interactive}
        doubleClickZoom={interactive}
        className="w-full h-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          url={tileUrl}
        />
        
        {/* Draw Route Line if available */}
        {route && route.length > 0 && (
          <Polyline positions={route} color="#38BDF8" weight={4} opacity={0.9} />
        )}
        
        {/* Draw Markers */}
        {markers.map((marker, idx) => (
          <Marker 
            key={idx} 
            position={[marker.lat, marker.lng]}
            icon={iconCache[marker.type] || iconCache.default}
          >
            {marker.popup && (
              <Popup className="font-sans rounded-xl text-gray-900">
                <div className="font-semibold">{marker.popup}</div>
              </Popup>
            )}
          </Marker>
        ))}
        
        <MapFitBounds markers={markers} route={route} />
      </MapContainer>
    </div>
  );
};

export default Map;
