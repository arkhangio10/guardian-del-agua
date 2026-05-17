"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { bboxAreaKm2, bboxSidesKm } from "@/utils/bbox";

interface Props {
  alert: any;
  apiBase: string;
  onClose: () => void;
}

interface Comparison {
  alert_id: string;
  contamination_type: string;
  before_date: string;
  after_date: string;
  before_offset_days: number;
  sentinel_hub_available: boolean;
  bands: { id: "rgb" | "nir" | "index"; label: string; available: boolean }[];
  phases: {
    before: { label: string; date: string; url_rgb: string; url_nir: string; url_index: string };
    after: { label: string; date: string; url_rgb: string; url_nir: string; url_index: string };
  };
}

type Band = "rgb" | "nir" | "index";

const TYPE_CHIP: Record<string, string> = {
  hydrocarbon: "bg-red-500/20 text-red-200 border-red-500/40",
  turbidity: "bg-orange-500/20 text-orange-200 border-orange-500/40",
  algal_bloom: "bg-green-500/20 text-green-200 border-green-500/40",
};

const IMG_FILTER = "contrast(1.35) saturate(1.5) brightness(1.05)";

export default function SatelliteLightbox({ alert, apiBase, onClose }: Props) {
  const tAlert = useTranslations("alert");
  const tContam = useTranslations("contamination");
  const tLight = useTranslations("lightbox");

  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [band, setBand] = useState<Band>("rgb");
  const [compareMode, setCompareMode] = useState(false);
  const [sliderPct, setSliderPct] = useState(50);

  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const dragRef = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);

  const stageRef = useRef<HTMLDivElement>(null);
  const sliderDragRef = useRef<boolean>(false);

  // Fetch /comparison descriptor
  useEffect(() => {
    let cancelled = false;
    fetch(`${apiBase}/detect/alerts/${alert.alert_id}/comparison`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled) return;
        setComparison(data);
        // Auto-enable compare mode when Sentinel Hub is configured (real before/after).
        if (data?.sentinel_hub_available) setCompareMode(true);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [apiBase, alert.alert_id]);

  // Keyboard shortcuts
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
    if (compareMode) return;
    e.preventDefault();
    setZoom((z) => Math.min(Math.max(z - e.deltaY * 0.002, 1), 6));
  };

  const onPointerDown = (e: React.PointerEvent) => {
    if (compareMode || zoom <= 1) return;
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

  // Slider drag (for compare mode)
  const updateSliderFromEvent = useCallback((clientX: number) => {
    if (!stageRef.current) return;
    const rect = stageRef.current.getBoundingClientRect();
    const pct = ((clientX - rect.left) / rect.width) * 100;
    setSliderPct(Math.max(0, Math.min(100, pct)));
  }, []);

  useEffect(() => {
    if (!compareMode) return;
    const onMove = (e: PointerEvent) => {
      if (sliderDragRef.current) updateSliderFromEvent(e.clientX);
    };
    const onUp = () => {
      sliderDragRef.current = false;
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [compareMode, updateSliderFromEvent]);

  const area = bboxAreaKm2(alert.sentinel_bbox);
  const sides = bboxSidesKm(alert.sentinel_bbox);
  const chipCls = TYPE_CHIP[alert.contamination_type] ?? "bg-slate-500/20 text-slate-200 border-slate-500/40";
  const typeKey = alert.contamination_type as "hydrocarbon" | "turbidity" | "algal_bloom";
  const typeLabel = typeKey in TYPE_CHIP ? tContam(typeKey) : alert.contamination_type;
  const claudeNote =
    alert.description ??
    (typeKey in TYPE_CHIP ? tContam(`${typeKey}_note` as any) : "");

  // URL builder per band+phase. Falls back to legacy /image (rgb/after) when no comparison data yet.
  function imageUrl(phase: "before" | "after"): string {
    if (!comparison) {
      return `${apiBase}/detect/alerts/${alert.alert_id}/image`;
    }
    const ph = comparison.phases[phase];
    return apiBase + (band === "nir" ? ph.url_nir : band === "index" ? ph.url_index : ph.url_rgb);
  }

  const singleUrl = imageUrl("after");
  const compareCanRender = compareMode && comparison;

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

        <div className="ml-auto flex items-center gap-2">
          {!compareMode && (
            <>
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
            </>
          )}
          {comparison?.sentinel_hub_available && (
            <button
              onClick={() => {
                setCompareMode((v) => !v);
                setZoom(1);
                setOffset({ x: 0, y: 0 });
              }}
              className={`ml-2 px-3 h-8 rounded-md text-[11px] font-semibold transition-colors ${
                compareMode
                  ? "bg-teal-500/30 text-teal-100 ring-1 ring-teal-400/60"
                  : "bg-slate-800/70 text-slate-200 hover:bg-slate-700"
              }`}
            >
              {compareMode ? tLight("compare_on") : tLight("compare_off")}
            </button>
          )}
          <button
            onClick={onClose}
            aria-label={tAlert("close")}
            className="ml-2 w-9 h-9 rounded-full bg-slate-800/70 hover:bg-slate-700 text-slate-200 flex items-center justify-center transition-colors"
          >
            ✕
          </button>
        </div>
      </header>

      {/* Band toggle */}
      {comparison && (
        <div
          className="flex-shrink-0 px-6 py-2 border-b border-slate-800/40 flex items-center gap-2 flex-wrap"
          onClick={(e) => e.stopPropagation()}
        >
          <span className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mr-1">
            {tLight("band_label")}
          </span>
          {comparison.bands.map((b) => {
            const isActive = b.id === band;
            const disabled = !b.available;
            return (
              <button
                key={b.id}
                onClick={() => !disabled && setBand(b.id)}
                disabled={disabled}
                title={disabled ? tLight("band_unavailable") : undefined}
                className={`px-3 py-1 rounded-full text-[11px] font-medium transition-colors ${
                  isActive
                    ? "bg-teal-500/20 text-teal-200 ring-1 ring-teal-400/40"
                    : disabled
                    ? "bg-slate-800/30 text-slate-600 cursor-not-allowed"
                    : "bg-slate-800/60 text-slate-300 hover:bg-slate-700"
                }`}
              >
                {b.label}
              </button>
            );
          })}
        </div>
      )}

      {/* Stage */}
      <div
        ref={stageRef}
        className="flex-1 min-h-0 relative overflow-hidden flex items-center justify-center select-none bg-slate-950"
        style={{ cursor: compareMode ? "default" : zoom > 1 ? "grab" : "zoom-in" }}
        onClick={(e) => {
          e.stopPropagation();
          if (!compareMode && zoom === 1) setZoom(2);
        }}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        {compareCanRender ? (
          <>
            {/* Layer A: "after" (full) */}
            <img
              src={imageUrl("after")}
              alt={tAlert("alt_satellite")}
              draggable={false}
              className="absolute inset-0 w-full h-full object-contain pointer-events-none"
              style={{ filter: IMG_FILTER }}
            />
            {/* Layer B: "before", clipped to show only the left sliderPct% */}
            <img
              src={imageUrl("before")}
              alt={`${tAlert("alt_satellite")} (${tLight("before")})`}
              draggable={false}
              className="absolute inset-0 w-full h-full object-contain pointer-events-none"
              style={{
                filter: IMG_FILTER,
                clipPath: `inset(0 ${100 - sliderPct}% 0 0)`,
              }}
            />
            {/* Slider handle */}
            <div
              className="absolute top-0 bottom-0 z-10"
              style={{ left: `${sliderPct}%`, transform: "translateX(-50%)", width: 40, cursor: "ew-resize" }}
              onPointerDown={(e) => {
                e.stopPropagation();
                sliderDragRef.current = true;
                updateSliderFromEvent(e.clientX);
              }}
            >
              <div className="absolute top-0 bottom-0 left-1/2 w-[2px] bg-teal-300/90 shadow-[0_0_12px_rgba(94,234,212,0.6)]" />
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-slate-950/85 border border-teal-300/70 flex items-center justify-center text-teal-200 backdrop-blur">
                <span className="text-xs font-mono">‹›</span>
              </div>
            </div>
            {/* Before label, left */}
            <div className="absolute top-3 left-3 px-2 py-1 rounded-md bg-slate-950/80 backdrop-blur text-[10px] uppercase tracking-wider text-slate-100 font-mono pointer-events-none">
              {tLight("before")} · {comparison.before_date}
            </div>
            {/* After label, right */}
            <div className="absolute top-3 right-3 px-2 py-1 rounded-md bg-slate-950/80 backdrop-blur text-[10px] uppercase tracking-wider text-teal-200 font-mono pointer-events-none">
              {tLight("after")} · {comparison.after_date}
            </div>
          </>
        ) : (
          <>
            <img
              src={singleUrl}
              alt={tAlert("alt_satellite")}
              draggable={false}
              className="max-w-full max-h-full object-contain transition-transform duration-100 pointer-events-none"
              style={{
                filter: IMG_FILTER,
                transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
                transformOrigin: "center center",
              }}
            />
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
          </>
        )}
      </div>

      {/* Bottom */}
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

        {compareCanRender && (
          <div className="flex items-center gap-3 text-[11px] text-slate-400">
            <span className="text-[10px] uppercase tracking-wider text-slate-500">
              {tLight("compare_mode_active")}
            </span>
            <span className="font-mono">
              {comparison.before_date} → {comparison.after_date}
            </span>
            <span className="text-slate-600">·</span>
            <span>{tLight("compare_hint")}</span>
          </div>
        )}

        {!compareCanRender && (
          <p className="text-[10px] text-slate-500 italic">{tLight("hint")}</p>
        )}
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
