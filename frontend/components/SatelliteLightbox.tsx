"use client";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { bboxAreaKm2, bboxSidesKm } from "@/utils/bbox";

interface Props {
  alert: any;
  apiBase: string;
  onClose: () => void;
}

const TYPE_CHIP: Record<string, string> = {
  hydrocarbon: "bg-red-500/20 text-red-200 border-red-500/40",
  turbidity: "bg-orange-500/20 text-orange-200 border-orange-500/40",
  algal_bloom: "bg-green-500/20 text-green-200 border-green-500/40",
};

export default function SatelliteLightbox({ alert, apiBase, onClose }: Props) {
  const tAlert = useTranslations("alert");
  const tContam = useTranslations("contamination");
  const tLight = useTranslations("lightbox");

  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const dragRef = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);
  const stageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "+" || e.key === "=") setZoom((z) => Math.min(z + 0.5, 6));
      if (e.key === "-" || e.key === "_") setZoom((z) => Math.max(z - 0.5, 1));
      if (e.key === "0") {
        setZoom(1);
        setOffset({ x: 0, y: 0 });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    setZoom((z) => Math.min(Math.max(z - e.deltaY * 0.002, 1), 6));
  };

  const onPointerDown = (e: React.PointerEvent) => {
    if (zoom <= 1) return;
    (e.target as Element).setPointerCapture(e.pointerId);
    dragRef.current = { x: e.clientX, y: e.clientY, ox: offset.x, oy: offset.y };
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragRef.current) return;
    setOffset({
      x: dragRef.current.ox + (e.clientX - dragRef.current.x),
      y: dragRef.current.oy + (e.clientY - dragRef.current.y),
    });
  };

  const onPointerUp = () => {
    dragRef.current = null;
  };

  const area = bboxAreaKm2(alert.sentinel_bbox);
  const sides = bboxSidesKm(alert.sentinel_bbox);
  const chipCls = TYPE_CHIP[alert.contamination_type] ?? "bg-slate-500/20 text-slate-200 border-slate-500/40";
  const typeKey = alert.contamination_type as "hydrocarbon" | "turbidity" | "algal_bloom";
  const typeLabel = typeKey in TYPE_CHIP ? tContam(typeKey) : alert.contamination_type;
  const claudeNote =
    alert.description ??
    (typeKey in TYPE_CHIP ? tContam(`${typeKey}_note` as any) : "");

  return (
    <div
      className="fixed inset-0 z-[100] bg-slate-950/95 backdrop-blur flex flex-col animate-fade-in"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      {/* Top bar */}
      <header
        className="flex-shrink-0 px-6 py-3 border-b border-slate-800/60 flex items-center gap-4"
        onClick={(e) => e.stopPropagation()}
      >
        <span
          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${chipCls}`}
        >
          {typeLabel}
        </span>
        <span className="text-sm font-semibold text-slate-100 truncate">
          {alert.attribution?.operator_name ?? tAlert("unknown_operator")}
        </span>
        <span className="hidden md:inline text-[11px] font-mono text-teal-300/80">
          {alert.sentinel_image_id ?? ""}
        </span>

        <div className="ml-auto flex items-center gap-2">
          <ZoomBtn label="−" onClick={() => setZoom((z) => Math.max(z - 0.5, 1))} />
          <span className="font-mono text-[11px] text-slate-300 w-12 text-center">
            {Math.round(zoom * 100)}%
          </span>
          <ZoomBtn label="+" onClick={() => setZoom((z) => Math.min(z + 0.5, 6))} />
          <ZoomBtn
            label={tLight("reset")}
            onClick={() => {
              setZoom(1);
              setOffset({ x: 0, y: 0 });
            }}
            wide
          />
          <button
            onClick={onClose}
            aria-label={tAlert("close")}
            className="ml-2 w-9 h-9 rounded-full bg-slate-800/70 hover:bg-slate-700 text-slate-200 flex items-center justify-center transition-colors"
          >
            ✕
          </button>
        </div>
      </header>

      {/* Stage */}
      <div
        ref={stageRef}
        className="flex-1 min-h-0 relative overflow-hidden flex items-center justify-center select-none"
        style={{ cursor: zoom > 1 ? "grab" : "zoom-in" }}
        onClick={(e) => {
          e.stopPropagation();
          if (zoom === 1) setZoom(2);
        }}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <img
          src={`${apiBase}/detect/alerts/${alert.alert_id}/image`}
          alt={tAlert("alt_satellite")}
          draggable={false}
          className="max-w-full max-h-full object-contain transition-transform duration-100 pointer-events-none"
          style={{
            filter: "contrast(1.35) saturate(1.5) brightness(1.05)",
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
            transformOrigin: "center center",
          }}
        />

        {/* Centroid crosshair when zoomed out */}
        {zoom === 1 && alert.contamination_type && (
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
            <div className="relative w-16 h-16">
              <div className="absolute inset-0 border-2 border-teal-300/70 rounded-full animate-pulse" />
              <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-teal-300 shadow-glow-teal" />
              <span className="absolute top-full left-1/2 -translate-x-1/2 mt-1 text-[10px] font-mono uppercase tracking-wider text-teal-200 whitespace-nowrap">
                {tLight("anomaly_zone")}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Bottom: Claude caption + bbox metadata */}
      <footer
        className="flex-shrink-0 border-t border-slate-800/60 px-6 py-4 space-y-3"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <span className="text-[10px] uppercase tracking-[0.18em] text-teal-300 font-semibold flex-shrink-0 mt-0.5">
            {tAlert("claude_label")}
          </span>
          <p className="text-sm text-slate-200 leading-relaxed">{claudeNote}</p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <MetaCell
            label={tLight("confidence")}
            value={`${(alert.confidence * 100).toFixed(0)}%`}
            accent
          />
          <MetaCell
            label={tLight("area_analyzed")}
            value={area != null ? `${area.toLocaleString()} km²` : "—"}
          />
          <MetaCell
            label={tLight("dimensions")}
            value={sides ? `${sides[0]} × ${sides[1]} km` : "—"}
          />
          <MetaCell
            label={tLight("bbox_wgs84")}
            value={
              alert.sentinel_bbox
                ? alert.sentinel_bbox.map((n: number) => n.toFixed(2)).join(", ")
                : "—"
            }
            mono
          />
        </div>

        <p className="text-[10px] text-slate-500 italic">{tLight("hint")}</p>
      </footer>
    </div>
  );
}

function ZoomBtn({ label, onClick, wide }: { label: string; onClick: () => void; wide?: boolean }) {
  return (
    <button
      onClick={onClick}
      className={`${
        wide ? "px-3" : "w-8"
      } h-8 rounded-md bg-slate-800/70 hover:bg-slate-700 text-slate-200 text-sm font-semibold transition-colors`}
    >
      {label}
    </button>
  );
}

function MetaCell({
  label,
  value,
  accent,
  mono,
}: {
  label: string;
  value: React.ReactNode;
  accent?: boolean;
  mono?: boolean;
}) {
  return (
    <div className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2">
      <div className="text-[9px] uppercase tracking-wider text-slate-500">{label}</div>
      <div
        className={`mt-0.5 ${accent ? "text-teal-300 font-bold text-sm" : "text-slate-200"} ${
          mono ? "font-mono text-[11px]" : ""
        }`}
      >
        {value}
      </div>
    </div>
  );
}
