/**
 * SliceTimeline — the signature element of this webapp.
 *
 * Visualises the relationship between a source audio's full duration
 * and the slice that was extracted to produce a given execution. This
 * is the operational truth of the system: a slice of audio becomes a
 * video. Rendering it as a precise horizontal bar (rather than two
 * numeric timestamps) lets the operator see at a glance:
 *   - where in the audio the slice sat (beginning / middle / end),
 *   - how much of the source was used (proportion),
 *   - the absolute duration of both.
 *
 * Tick marks every 10% with mono timestamps. The selected slice is
 * filled with the oxblood accent — the only place on the page that
 * colour is used for emphasis rather than status.
 *
 * The bar is rendered with CSS only (no canvas / SVG) so it scales
 * fluidly and prints cleanly.
 */

import { formatDuration } from "@/lib/format";

export function SliceTimeline({
  audioDuration,
  audioName,
  sliceStart,
  sliceEnd,
  sliceDuration,
}: {
  audioDuration: number;
  audioName?: string;
  sliceStart: number;
  sliceEnd: number;
  sliceDuration: number;
}) {
  const safeTotal = Math.max(audioDuration, 0.001);
  const startPct = Math.max(0, Math.min(100, (sliceStart / safeTotal) * 100));
  const endPct = Math.max(0, Math.min(100, (sliceEnd / safeTotal) * 100));
  const widthPct = Math.max(0.5, endPct - startPct); // min 0.5% so it's visible

  // 10 tick marks at 0%, 10%, …, 100%.
  const ticks = Array.from({ length: 11 }, (_, i) => i * 10);

  return (
    <figure className="my-6">
      {/* Header: title + audio reference */}
      <div className="flex items-baseline justify-between hairline-b pb-2 mb-4">
        <div>
          <div className="eyebrow mb-1">SLICE WITHIN SOURCE AUDIO</div>
          {audioName && (
            <div className="font-serif text-base italic text-mute">
              {audioName}
            </div>
          )}
        </div>
        <div className="text-right">
          <div className="num text-sm">
            {formatDuration(sliceDuration)}
            <span className="text-mute"> / {formatDuration(audioDuration)}</span>
          </div>
          <div className="eyebrow mt-1">SLICE / TOTAL</div>
        </div>
      </div>

      {/* The bar */}
      <div className="relative">
        {/* Tick labels above the bar */}
        <div className="relative h-4 mb-1">
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
          className="relative h-8 bg-rule/[0.08] hairline-all"
          role="img"
          aria-label={`Slice from ${formatDuration(sliceStart)} to ${formatDuration(
            sliceEnd,
          )} of a ${formatDuration(audioDuration)} source`}
        >
          {/* Selected slice */}
          <div
            className="absolute inset-y-0 bg-accent/85 hairline-r hairline-l"
            style={{ left: `${startPct}%`, width: `${widthPct}%` }}
          >
            {/* Slice label, centered if there's room */}
            {widthPct > 12 && (
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="num text-2xs text-paper font-medium">
                  {formatDuration(sliceDuration)}
                </span>
              </div>
            )}
          </div>

          {/* Tick marks on the track */}
          {ticks.map((t) => (
            <div
              key={t}
              className="absolute top-0 bottom-0 w-px bg-rule/20"
              style={{ left: `${t}%` }}
              aria-hidden
            />
          ))}
        </div>

        {/* Start / end markers below */}
        <div className="relative h-4 mt-1">
          <span
            className="absolute num text-2xs text-accent -translate-x-1/2 font-medium"
            style={{ left: `${startPct}%` }}
          >
            ▲ {formatDuration(sliceStart)}
          </span>
          <span
            className="absolute num text-2xs text-accent -translate-x-1/2 font-medium"
            style={{ left: `${endPct}%` }}
          >
            ▲ {formatDuration(sliceEnd)}
          </span>
        </div>
      </div>

      {/* Legend */}
      <figcaption className="mt-6 flex items-center gap-6 text-2xs text-mute font-mono uppercase tracking-wide-2">
        <span className="flex items-center gap-2">
          <span className="inline-block w-3 h-2 bg-accent/85" />
          Selected slice
        </span>
        <span className="flex items-center gap-2">
          <span className="inline-block w-3 h-2 bg-rule/[0.08] hairline-all" />
          Source audio
        </span>
      </figcaption>
    </figure>
  );
}
