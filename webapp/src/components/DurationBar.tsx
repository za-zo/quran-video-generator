/**
 * DurationBar — a thin horizontal bar visualising a duration as a
 * proportion of a reference maximum.
 *
 * NOTE: This component is retained for slice-detail contexts where the
 * proportional relationship is genuinely informative. List tables no
 * longer use it — see the user request to "remove the duration bar in
 * all tables, show only the text duration".
 */

export function DurationBar({
  value,
  max,
  label,
  className = "",
}: {
  value: number;
  max: number;
  label?: string;
  className?: string;
}) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="flex-1 h-px bg-rule relative">
        <div
          className="absolute -inset-y-px left-0 bg-ink"
          style={{ width: `${pct}%`, height: "3px", top: "-1px" }}
          aria-hidden
        />
      </div>
      {label && (
        <span className="num text-2xs text-mute w-16 text-right">{label}</span>
      )}
    </div>
  );
}
