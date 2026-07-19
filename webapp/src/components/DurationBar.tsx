/**
 * DurationBar — a thin horizontal bar visualising a duration as a
 * proportion of a reference maximum.
 *
 * Recurring motif across list pages: each audio/video row gets one so
 * duration becomes a visual quantity, not just a number. The bar uses
 * the rule colour at low opacity so a sea of them reads as a quiet
 * field, with the filled portion in solid ink for contrast.
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
      <div className="flex-1 h-1 bg-rule/15 relative">
        <div
          className="absolute inset-y-0 left-0 bg-ink"
          style={{ width: `${pct}%` }}
          aria-hidden
        />
      </div>
      {label && (
        <span className="num text-2xs text-mute w-16 text-right">{label}</span>
      )}
    </div>
  );
}
