import { Icon } from "./Icon";
import type { Comparison } from "../compare";

export function ComparisonView({ comparison }: { comparison: Comparison }) {
  return (
    <div className="comparison">
      {comparison.comparable ? (
        <div className="verification-result pass comparison-verdict">
          <Icon name="check" />
          <span>
            <strong>Comparable</strong>
            Same model, dataset, seed and sample population — the deltas isolate the change.
          </span>
        </div>
      ) : (
        <div className="verification-result fail comparison-verdict">
          <Icon name="close" />
          <span>
            <strong>Not a controlled comparison</strong>
            The runs differ in ways that make the deltas arithmetic, not findings.
          </span>
        </div>
      )}

      {comparison.blockers.map((reason) => (
        <div className="attack-warning blocker" key={reason}>
          <Icon name="close" size={16} />
          <span>{reason}</span>
        </div>
      ))}

      {comparison.sections.map((section) => (
        <section className="comparison-section" key={section.title}>
          <div className="comparison-head">
            <span>{section.title}</span>
            <span>A</span>
            <span>B</span>
            <span>Δ</span>
          </div>
          {section.rows.map((row) => (
            <div
              className={`comparison-row ${row.differs ? "differs" : ""} ${
                row.provenance ? "provenance" : ""
              }`}
              key={row.label}
            >
              <span className="comparison-label">{row.label}</span>
              <span className="mono">{row.left}</span>
              <span className="mono">{row.right}</span>
              <span className={`comparison-delta ${row.delta?.direction ?? ""}`}>
                {row.delta ? row.delta.text : row.differs ? "changed" : "—"}
              </span>
            </div>
          ))}
        </section>
      ))}

      {comparison.notes.map((note) => (
        <div className="attack-warning" key={note}>
          <Icon name="activity" size={16} />
          <span>{note}</span>
        </div>
      ))}
    </div>
  );
}
