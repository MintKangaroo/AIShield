import { formatPercent } from "../format";
import type { AttackRunRecord } from "../types";

export function StrengthCurve({ runs }: { runs: AttackRunRecord[] }) {
  if (!runs.length) return null;
  const points = [...runs].sort((left, right) => left.config.epsilon - right.config.epsilon);
  const width = 520;
  const height = 180;
  const pad = 28;
  const minEpsilon = points[0].config.epsilon;
  const maxEpsilon = points[points.length - 1].config.epsilon || 1;
  const x = (epsilon: number) =>
    pad + ((epsilon - minEpsilon) / Math.max(maxEpsilon - minEpsilon, 1e-6)) * (width - pad * 2);
  const y = (accuracy: number) => height - pad - accuracy * (height - pad * 2);
  const path = points
    .map(
      (run, index) =>
        `${index ? "L" : "M"}${x(run.config.epsilon)},${y(run.metrics.robust_accuracy)}`,
    )
    .join(" ");
  return (
    <div className="curve-card">
      <div className="panel-heading">
        <div>
          <span className="kicker">강도 곡선</span>
          <h3>{points[0].config.algorithm.toUpperCase()} robust 정확도</h3>
        </div>
        <span className="mono faint">{points.length} evidence points</span>
      </div>
      <svg
        aria-label="엡실론별 robust 정확도"
        className="curve-chart"
        role="img"
        viewBox={`0 0 ${width} ${height}`}
      >
        <path className="curve-axis" d={`M${pad},${pad}V${height - pad}H${width - pad}`} />
        <path className="curve-line" d={path} />
        {points.map((run) => (
          <circle cx={x(run.config.epsilon)} cy={y(run.metrics.robust_accuracy)} key={run.id} r="4">
            <title>{`ε ${run.config.epsilon.toFixed(4)} · ${formatPercent(run.metrics.robust_accuracy)}`}</title>
          </circle>
        ))}
      </svg>
      <div className="curve-legend">
        <span>robust 정확도</span>
        <span>
          ε {minEpsilon.toFixed(3)} → {maxEpsilon.toFixed(3)}
        </span>
      </div>
    </div>
  );
}
