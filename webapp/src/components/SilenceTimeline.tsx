/**
 * SilenceTimeline — visualises the cached silence positions detected in
 * a source audio.
 *
 * Same visual language as SliceTimeline: a horizontal track representing
 * the full audio duration, with tick marks every 10%. Instead of a
 * selected slice, each silence position is rendered as a thin vertical
 * bar (colour `bg-rule` — neutral, not oxblood, because silences are
 * metadata, not the operational truth the way a slice is).
 *
 * Hovering a silence bar shows a native tooltip
 * (`{position_seconds}s · {duration_ms}ms`).
 *
 * The header shows the count of positions and the analysis date. If 0
 * positions were detected, a small "Aucune position détectée" message
 * replaces the legend.
 */

import { formatDuration, formatTimestamp } from "@/lib/format";

export function SilenceTimeline({
  audioDuration,
  audioName,
  positions,
  analyzedAt,
}: {
  audioDuration: number;
  audioName?: string;
  positions: Array<{ position_seconds: number; duration_ms: number }>;
  analyzedAt?: Date | string | null;
}) {
  const safeTotal = Math.max(audioDuration, 0.001);
  const ticks = Array.from({ length: 11 }, (_, i) => i * 10);
  const hasPositions = positions && positions.length > 0;

  return (
    <figure className="my-6">
      {/* Header: title + audio reference */}
      <div className="flex items-baseline justify-between hairline-b pb-3 mb-6 gap-4 flex-wrap">
        <div className="min-w-0">
          <div className="eyebrow mb-2">
            {hasPositions
              ? `${positions.length} POSITION${positions.length > 1 ? "S" : ""}`
              : "AUCUNE POSITION DÉTECTÉE"}
            {analyzedAt && (
              <span className="text-mute ml-2 normal-case tracking-normal">
                · analysé le {formatTimestamp(analyzedAt)}
              </span>
            )}
          </div>
          {audioName && (
            <div
              className="font-serif text-lg italic text-mute truncate"
              title={audioName}
            >
              {audioName}
            </div>
          )}
        </div>
        <div className="text-right shrink-0">
          <div className="num text-base text-ink">
            {formatDuration(audioDuration)}
          </div>
          <div className="eyebrow mt-1">DURÉE TOTALE</div>
        </div>
      </div>

      {/* The bar */}
      <div className="relative">
        {/* Tick labels above the bar */}
        <div className="relative h-4 mb-2">
          {ticks.map((t) => (
            <span
              key={t}
              className="absolute num text-2xs text-mute -translate-x-1/2"
              style={{ left: `${t}%` }}
            >
              {formatDuration((t / 100) * safeTotal)}
            </span>
          ))}
        </div>

        {/* Track */}
        <div
          className="relative h-10 bg-paperRaised hairline-b"
          role="img"
          aria-label={`Silence positions for a ${formatDuration(audioDuration)} source audio`}
        >
          {/* Tick marks on the track */}
          {ticks.map((t) => (
            <div
              key={t}
              className="absolute top-0 bottom-0 w-px bg-rule"
              style={{ left: `${t}%` }}
              aria-hidden
            />
          ))}

          {/* Silence position bars */}
          {hasPositions &&
            positions.map((p, i) => {
              const pct = Math.max(
                0,
                Math.min(100, (p.position_seconds / safeTotal) * 100),
              );
              const tooltip = `${p.position_seconds.toFixed(2)}s · ${p.duration_ms}ms`;
              return (
                <div
                  key={`${p.position_seconds}-${i}`}
                  className="absolute top-0 bottom-0 w-px bg-ink"
                  style={{ left: `${pct}%` }}
                  title={tooltip}
                  aria-label={tooltip}
                />
              );
            })}
        </div>

        {/* Empty-state message below the track when no positions */}
        {!hasPositions && (
          <div className="relative h-4 mt-2">
            <span className="absolute left-0 num text-2xs text-mute italic">
              Aucune position détectée
            </span>
          </div>
        )}
      </div>

      {/* Legend */}
      <figcaption className="mt-8 flex items-center gap-6 text-2xs text-mute font-mono uppercase tracking-wide-2">
        <span className="flex items-center gap-2">
          <span className="inline-block w-3 h-2 bg-ink" />
          Position de silence
        </span>
        <span className="flex items-center gap-2">
          <span className="inline-block w-3 h-2 bg-paperRaised hairline-b" />
          Source audio
        </span>
      </figcaption>
    </figure>
  );
}
