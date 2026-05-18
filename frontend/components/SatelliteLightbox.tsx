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

const BAND_GLYPH: Record<Band, string> = {
  rgb: "RGB",
  nir: "NIR",
  index: "IDX",
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
  const [infoCollapsed, setInfoCollapsed] = useState(false);

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
      if (e.key === "i") setInfoCollapsed((v) => !v);
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

  // CSS scale alone amplifies a downsampled PNG (pixelated). For real detail,
  // ask the backend to crop the bbox toward the centroid at higher zoom levels —
  // each tier returns 1024² over a smaller footprint, giving more m/px.
  // Tier boundaries chosen so the URL only changes twice across the 1×→6× range.
  function zoomPctForCss(z: number): number {
    if (z >= 4) return 25;
    if (z >= 2) return 50;
    return 100;
  }

  function imageUrl(phase: "before" | "after"): string {
    const zp = zoomPctForCss(zoom);
    if (!comparison) {
      return `${apiBase}/detect/alerts/${alert.alert_id}/image?zoom_pct=${zp}`;
    }
    const ph = comparison.phases[phase];
    const base = band === "nir" ? ph.url_nir : band === "index" ? ph.url_index : ph.url_rgb;
    const sep = base.includes("?") ? "&" : "?";
    return `${apiBase}${base}${sep}zoom_pct=${zp}`;
  }

  const singleUrl = imageUrl("after");
  const compareCanRender = compareMode && comparison;
  const nativeZoomActive = !compareCanRender && zoom >= 2;

  // When tier boundary is crossed, the new image is centered on the bbox
  // centroid so the user's panning offset is no longer meaningful — reset.
  const tierRef = useRef(zoomPctForCss(zoom));
  useEffect(() => {
    const t = zoomPctForCss(zoom);
    if (t !== tierRef.current) {
      tierRef.current = t;
      setOffset({ x: 0, y: 0 });
    }
  }, [zoom]);

  return (
    <div
      className="fixed inset-0 z-[100] bg-slate-950/95 backdrop-blur flex flex-col animate-fade-in"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      {/* Top bar — slim, only essential controls */}
      <header
        className="flex-shrink-0 h-12 px-4 sm:px-6 border-b border-slate-800/60 flex items-center gap-2 sm:gap-3"
        onClick={(e) => e.stopPropagation()}
      >
        <span
          className={`flex-shrink-0 inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-semibold border ${chipCls}`}
        >
          {typeLabel}
        </span>
        <span className="hidden md:block min-w-0 flex-shrink text-sm font-semibold text-slate-100 truncate">
          {alert.attribution?.operator_name ?? tAlert("unknown_operator")}
        </span>

        <div className="ml-auto flex items-center gap-1.5 flex-shrink-0">
          {!compareMode && (
            <>
              {nativeZoomActive && (
                <span
                  className="hidden md:inline-flex items-center gap-1 px-2 h-7 rounded-md bg-teal-500/15 text-teal-200 text-[10px] uppercase tracking-wider font-mono ring-1 ring-teal-400/30"
                  title={tLight("native_zoom_hint")}
                >
                  ⊕ {tLight("native_zoom")}
                </span>
              )}
              <div className="hidden sm:flex items-center gap-1 mr-1 px-1.5 py-0.5 rounded-md bg-slate-900/60 border border-slate-700/40">
                <ZoomBtn label="−" onClick={() => setZoom((z) => Math.max(z - 0.5, 1))} />
                <span className="font-mono text-[10px] text-slate-300 w-10 text-center select-none">
                  {Math.round(zoom * 100)}%
                </span>
                <ZoomBtn label="+" onClick={() => setZoom((z) => Math.min(z + 0.5, 6))} />
              </div>
            </>
          )}
          {comparison?.sentinel_hub_available && (
            <button
              onClick={() => {
                setCompareMode((v) => !v);
                setZoom(1);
                setOffset({ x: 0, y: 0 });
              }}
              className={`px-2.5 sm:px-3 h-8 rounded-md text-[11px] font-semibold transition-colors flex items-center gap-1.5 ${
                compareMode
                  ? "bg-teal-500/25 text-teal-100 ring-1 ring-teal-400/50"
                  : "bg-slate-800/70 text-slate-200 hover:bg-slate-700"
              }`}
            >
              <span className="inline-block w-2 h-2 rounded-full bg-current opacity-70" />
              <span className="hidden sm:inline">
                {compareMode ? tLight("compare_on") : tLight("compare_off")}
              </span>
              <span className="sm:hidden">{compareMode ? "⇋" : "⇉"}</span>
            </button>
          )}
          <button
            onClick={() => setInfoCollapsed((v) => !v)}
            aria-label="Toggle info"
            title="(i) — info"
            className={`hidden sm:flex w-8 h-8 rounded-md items-center justify-center text-sm font-semibold transition-colors ${
              infoCollapsed
                ? "bg-slate-800/70 text-slate-400 hover:bg-slate-700"
                : "bg-teal-500/15 text-teal-200 ring-1 ring-teal-400/30"
            }`}
          >
            ⓘ
          </button>
          <button
            onClick={onClose}
            aria-label={tAlert("close")}
            className="w-8 h-8 rounded-md bg-slate-800/70 hover:bg-slate-700 text-slate-200 flex items-center justify-center transition-colors"
          >
            ✕
          </button>
        </div>
      </header>

      {/* Band toggle — segmented control, never wraps */}
      {comparison && (
        <div
          className="flex-shrink-0 px-4 sm:px-6 py-2 border-b border-slate-800/40 flex items-center gap-3"
          onClick={(e) => e.stopPropagation()}
        >
          <span className="hidden sm:inline text-[10px] uppercase tracking-[0.18em] text-slate-500 font-semibold flex-shrink-0">
            {tLight("band_label")}
          </span>
          <div
            role="tablist"
            className="flex items-center gap-0.5 p-0.5 rounded-lg bg-slate-900/70 border border-slate-700/40 flex-shrink-0"
          >
            {comparison.bands.map((b) => {
              const isActive = b.id === band;
              const disabled = !b.available;
              return (
                <button
                  key={b.id}
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => !disabled && setBand(b.id)}
                  disabled={disabled}
                  title={disabled ? tLight("band_unavailable") : b.label}
                  className={`px-3 h-7 rounded-md text-[11px] font-semibold transition-all flex items-center gap-1.5 ${
                    isActive
                      ? "bg-teal-500/25 text-teal-100 shadow-sm"
                      : disabled
                      ? "text-slate-600 cursor-not-allowed"
                      : "text-slate-300 hover:bg-slate-800/80"
                  }`}
                >
                  <span className="font-mono text-[10px] opacity-80">{BAND_GLYPH[b.id]}</span>
                  <span className="hidden md:inline">{b.label}</span>
                </button>
              );
            })}
          </div>
          {compareCanRender && (
            <div className="ml-auto hidden md:flex items-center gap-2 text-[10px] font-mono text-slate-500">
              <span>{comparison.before_date}</span>
              <span className="text-teal-400">⇄</span>
              <span className="text-teal-300">{comparison.after_date}</span>
            </div>
          )}
        </div>
      )}

      {/* Stage — image as hero */}
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
            <img
              src={imageUrl("after")}
              alt={tAlert("alt_satellite")}
              draggable={false}
              className="absolute inset-0 w-full h-full object-contain pointer-events-none"
              style={{ filter: IMG_FILTER }}
            />
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

            {/* Slider — full-height vertical line + big grip */}
            <div
              className="absolute top-0 bottom-0 z-10 pointer-events-auto"
              style={{ left: `${sliderPct}%`, transform: "translateX(-50%)", width: 56 }}
              onPointerDown={(e) => {
                e.stopPropagation();
                sliderDragRef.current = true;
                updateSliderFromEvent(e.clientX);
              }}
            >
              <div
                className="absolute top-0 bottom-0 left-1/2 w-[3px] -translate-x-1/2"
                style={{
                  background:
                    "linear-gradient(180deg, rgba(94,234,212,0.0) 0%, rgba(94,234,212,0.9) 12%, rgba(94,234,212,0.9) 88%, rgba(94,234,212,0.0) 100%)",
                  boxShadow: "0 0 16px rgba(94,234,212,0.55)",
                  cursor: "ew-resize",
                }}
              />
              {/* Grip */}
              <div
                className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-14 h-14 rounded-full flex items-center justify-center text-teal-100 backdrop-blur"
                style={{
                  background:
                    "radial-gradient(circle at center, rgba(13,148,136,0.95) 0%, rgba(8,15,26,0.95) 70%)",
                  border: "1.5px solid rgba(94,234,212,0.8)",
                  boxShadow: "0 0 24px rgba(94,234,212,0.45), inset 0 1px 0 rgba(255,255,255,0.15)",
                  cursor: "ew-resize",
                }}
              >
                <span className="text-base font-bold tracking-tighter select-none">‹ ›</span>
              </div>
              {/* Drag dots above/below for affordance */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
                <div className="absolute -top-12 left-1/2 -translate-x-1/2 flex gap-0.5">
                  <span className="w-0.5 h-0.5 rounded-full bg-teal-300/40" />
                  <span className="w-0.5 h-0.5 rounded-full bg-teal-300/60" />
                  <span className="w-0.5 h-0.5 rounded-full bg-teal-300/40" />
                </div>
                <div className="absolute top-12 left-1/2 -translate-x-1/2 flex gap-0.5">
                  <span className="w-0.5 h-0.5 rounded-full bg-teal-300/40" />
                  <span className="w-0.5 h-0.5 rounded-full bg-teal-300/60" />
                  <span className="w-0.5 h-0.5 rounded-full bg-teal-300/40" />
                </div>
              </div>
            </div>

            {/* Before/after labels on image — big, integrated */}
            <div className="absolute top-4 left-4 z-20 pointer-events-none">
              <div className="px-3 py-1.5 rounded-lg bg-slate-950/85 border border-slate-700/40 backdrop-blur">
                <div className="text-[9px] uppercase tracking-[0.18em] text-slate-400 font-semibold">
                  {tLight("before")}
                </div>
                <div className="font-mono text-xs text-slate-100 mt-0.5">
                  {comparison.before_date}
                </div>
              </div>
            </div>
            <div className="absolute top-4 right-4 z-20 pointer-events-none">
              <div className="px-3 py-1.5 rounded-lg bg-teal-500/15 border border-teal-400/40 backdrop-blur">
                <div className="text-[9px] uppercase tracking-[0.18em] text-teal-300 font-semibold">
                  {tLight("after")}
                </div>
                <div className="font-mono text-xs text-teal-100 mt-0.5">
                  {comparison.after_date}
                </div>
              </div>
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
                // Compensate CSS scale by the native-crop tier so the visual
                // zoom feels continuous as the URL changes underneath. At
                // zoom=2 with zoom_pct=50 the image already shows the central
                // 50% (2× native), so css scale becomes 1; at zoom=3 css = 1.5;
                // at zoom=4 with zoom_pct=25 css = 1 again, etc.
                transform: `translate(${offset.x}px, ${offset.y}px) scale(${
                  (zoom * zoomPctForCss(zoom)) / 100
                })`,
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

        {/* Floating Claude reasoning chip on image (collapses with infoCollapsed) */}
        {!infoCollapsed && claudeNote && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 max-w-xl w-[calc(100%-2rem)] pointer-events-none">
            <div className="glass rounded-xl border border-teal-500/30 px-4 py-2.5 flex items-start gap-3 shadow-glow-teal">
              <span className="text-[10px] uppercase tracking-[0.18em] text-teal-300 font-semibold flex-shrink-0 mt-0.5">
                {tAlert("claude_label")}
              </span>
              <p className="text-[12px] sm:text-sm text-slate-100 leading-snug">{claudeNote}</p>
            </div>
          </div>
        )}
      </div>

      {/* Bottom — compact stats only, dates already on image */}
      {!infoCollapsed && (
        <footer
          className="flex-shrink-0 border-t border-slate-800/60 px-4 sm:px-6 py-2.5 flex items-center gap-3 overflow-x-auto gda-scroll"
          onClick={(e) => e.stopPropagation()}
        >
          <StatPill label={tLight("confidence")} value={`${(alert.confidence * 100).toFixed(0)}%`} accent />
          <StatPill
            label={tLight("area_analyzed")}
            value={area != null ? `${area.toLocaleString()} km²` : "—"}
          />
          <StatPill
            label={tLight("dimensions")}
            value={sides ? `${sides[0]} × ${sides[1]} km` : "—"}
          />
          <StatPill
            label={tLight("bbox_wgs84")}
            value={
              alert.sentinel_bbox
                ? alert.sentinel_bbox.map((n: number) => n.toFixed(2)).join(", ")
                : "—"
            }
            mono
          />
          <div className="hidden md:flex ml-auto flex-shrink-0 text-[10px] text-slate-500 italic items-center gap-2">
            {compareCanRender ? tLight("compare_hint") : tLight("hint")}
          </div>
        </footer>
      )}
    </div>
  );
}

function ZoomBtn({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-6 h-6 rounded text-slate-200 text-sm font-semibold hover:bg-slate-700 transition-colors flex items-center justify-center"
    >
      {label}
    </button>
  );
}

function StatPill({
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
    <div className="flex-shrink-0 flex items-baseline gap-2 px-3 py-1.5 rounded-lg bg-slate-900/60 border border-slate-700/40 whitespace-nowrap">
      <span className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold">
        {label}
      </span>
      <span
        className={`${accent ? "text-teal-300 font-bold text-sm" : "text-slate-200 text-xs font-semibold"} ${
          mono ? "font-mono text-[10px]" : ""
        }`}
      >
        {value}
      </span>
    </div>
  );
}
