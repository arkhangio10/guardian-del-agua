"use client";
import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import maplibregl, { StyleSpecification } from "maplibre-gl";
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

const SATELLITE_STYLE: StyleSpecification = {
  version: 8,
  glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
  sources: {
    "esri-imagery": {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      attribution:
        "Imagery © Esri, Maxar, Earthstar Geographics, USDA, USGS, AeroGRID, IGN, and the GIS User Community",
      maxzoom: 19,
    },
    "esri-reference": {
      type: "raster",
      tiles: [
        "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      maxzoom: 13,
    },
  },
  layers: [
    { id: "imagery", type: "raster", source: "esri-imagery" },
    {
      id: "imagery-darken",
      type: "background",
      paint: {
        "background-color": "#050b14",
        "background-opacity": 0.32,
      },
    },
    {
      id: "reference",
      type: "raster",
      source: "esri-reference",
      paint: { "raster-opacity": 0.75 },
    },
  ],
};

export default function Map({ alerts, selectedId, onSelect }: Props) {
  const tAlert = useTranslations("alert");
  const tContam = useTranslations("contamination");

  const mapRef = useRef<maplibregl.Map | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      style: SATELLITE_STYLE,
      center: [-75.5, -4.2],
      zoom: 6.2,
      attributionControl: false,
    });

    mapRef.current.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      "bottom-right"
    );
    mapRef.current.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
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

      const root = document.createElement("div");
      root.className = `gda-marker ${isSelected ? "gda-marker--selected" : ""}`;
      root.style.color = color;

      const ripple = document.createElement("div");
      ripple.className = "gda-marker__ripple";
      root.appendChild(ripple);

      const dot = document.createElement("div");
      dot.className = "gda-marker__dot";
      dot.style.background = color;
      root.appendChild(dot);

      const operator = alert.attribution?.operator_name ?? tAlert("detecting");
      const typeKey =
        alert.contamination_type === "hydrocarbon"
          ? "hydrocarbon_short"
          : alert.contamination_type === "turbidity"
          ? "turbidity_short"
          : alert.contamination_type === "algal_bloom"
          ? "algal_bloom_short"
          : null;
      const typeLabel = typeKey ? tContam(typeKey as any) : alert.contamination_type;
      const confidenceLabel = tAlert("confidence");

      const popup = new maplibregl.Popup({
        offset: 16,
        closeButton: false,
        className: "gda-popup",
      }).setHTML(
        `<div style="min-width:160px;">
          <div style="font-weight:600;color:#e2e8f0;margin-bottom:2px;">${escapeHtml(
            operator
          )}</div>
          <div style="color:#94a3b8;font-size:11px;">
            ${escapeHtml(typeLabel)} · ${(alert.confidence * 100).toFixed(0)}% ${escapeHtml(
          confidenceLabel
        )}
          </div>
          ${
            alert.predictions
              ? `<div style="color:#fca5a5;font-size:11px;margin-top:2px;">${escapeHtml(
                  tAlert("affected_30d_long", {
                    count: alert.predictions.people_affected_30d?.toLocaleString() ?? "—",
                  })
                )}</div>`
              : ""
          }
        </div>`
      );

      const marker = new maplibregl.Marker({ element: root })
        .setLngLat([lon, lat])
        .setPopup(popup)
        .addTo(mapRef.current!);

      root.addEventListener("click", (e) => {
        e.stopPropagation();
        onSelect(alert.alert_id);
        if (mapRef.current) {
          mapRef.current.flyTo({
            center: [lon, lat],
            zoom: Math.max(mapRef.current.getZoom(), 8),
            speed: 0.8,
          });
        }
      });
      root.addEventListener("mouseenter", () => marker.togglePopup());
      root.addEventListener("mouseleave", () => marker.togglePopup());

      markersRef.current.push(marker);
    });
  }, [alerts, selectedId, onSelect, tAlert, tContam]);

  return <div ref={containerRef} className="w-full h-full" />;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
