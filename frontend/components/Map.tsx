"use client";
import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

const TYPE_COLOR: Record<string, string> = {
  hydrocarbon: "#ef4444",
  turbidity: "#f97316",
  algal_bloom: "#22c55e",
};

interface Alert {
  alert_id: string;
  contamination_type: string;
  confidence: number;
  sentinel_bbox: number[];
  attribution?: { operator_name: string };
  predictions?: { people_affected_30d: number };
}

interface Props {
  alerts: Alert[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export default function Map({ alerts, selectedId, onSelect }: Props) {
  const mapRef = useRef<maplibregl.Map | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      style: process.env.NEXT_PUBLIC_MAPLIBRE_STYLE ?? "https://demotiles.maplibre.org/style.json",
      center: [-76.0, -4.2],
      zoom: 6,
    });

    mapRef.current.addControl(new maplibregl.NavigationControl(), "top-right");
  }, []);

  useEffect(() => {
    if (!mapRef.current) return;
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    alerts.forEach((alert) => {
      const [lonMin, latMin, lonMax, latMax] = alert.sentinel_bbox;
      const lon = (lonMin + lonMax) / 2;
      const lat = (latMin + latMax) / 2;

      const color = TYPE_COLOR[alert.contamination_type] ?? "#94a3b8";
      const isSelected = alert.alert_id === selectedId;

      const el = document.createElement("div");
      el.style.cssText = `
        width: ${isSelected ? 20 : 14}px;
        height: ${isSelected ? 20 : 14}px;
        border-radius: 50%;
        background: ${color};
        border: 2px solid ${isSelected ? "white" : "rgba(255,255,255,0.4)"};
        cursor: pointer;
        transition: all 0.2s;
        box-shadow: 0 0 ${isSelected ? 12 : 6}px ${color}80;
      `;

      const popup = new maplibregl.Popup({ offset: 12, closeButton: false }).setHTML(
        `<div style="color:#1a1a1a;font-size:12px;padding:4px;">
          <strong>${alert.attribution?.operator_name ?? "Detectando..."}</strong><br/>
          ${alert.contamination_type} · ${(alert.confidence * 100).toFixed(0)}% confianza<br/>
          ${alert.predictions ? `${alert.predictions.people_affected_30d?.toLocaleString("es-PE")} afectados` : ""}
        </div>`
      );

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([lon, lat])
        .setPopup(popup)
        .addTo(mapRef.current!);

      el.addEventListener("click", () => onSelect(alert.alert_id));
      markersRef.current.push(marker);
    });
  }, [alerts, selectedId, onSelect]);

  return <div ref={containerRef} className="w-full h-full" />;
}
