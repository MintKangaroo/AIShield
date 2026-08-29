import { Icon } from "../components/Icon";
import { JournalTable } from "../components/JournalTable";
import type { JournalEntry, JournalReplaySummary } from "../types";

export function JournalPage({
  busy,
  entries,
  onReplay,
  summary,
}: {
  busy: boolean;
  entries: JournalEntry[];
  onReplay: () => void;
  summary: JournalReplaySummary | null;
}) {
  return (
    <div className="page-content">
      <section className="registry-summary">
        <div>
          <span className="summary-icon">
            <Icon name="book" size={26} />
          </span>
          <div>
            <h2>Append-only metadata journal</h2>
            <p>
              Every registry record is written to <code>registry/journal.jsonl</code> as canonical
              JSON and flushed before the API returns it. Entries are never rewritten or deleted.
            </p>
          </div>
        </div>
        <span className="policy-pill">
          <i /> {entries.length} entries
        </span>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="kicker">Restart recovery</span>
            <h3>Replay the journal</h3>
          </div>
          <button
            className="button secondary compact"
            disabled={busy || !entries.length}
            type="button"
            onClick={onReplay}
          >
            <Icon name="refresh" size={15} />
            {busy ? "Replaying…" : "Replay journal"}
          </button>
        </div>
        {summary ? (
          <>
            <dl className="score-facts replay-facts">
              <div>
                <dt>Entries read</dt>
                <dd>{summary.entries_read}</dd>
              </div>
              <div>
                <dt>Datasets</dt>
                <dd>{summary.datasets_restored}</dd>
              </div>
              <div>
                <dt>Models</dt>
                <dd>{summary.models_restored}</dd>
              </div>
              <div>
                <dt>Runs</dt>
                <dd>
                  {summary.baselines_restored +
                    summary.attacks_restored +
                    summary.defenses_restored +
                    summary.transfers_restored +
                    summary.training_restored}
                </dd>
              </div>
              <div>
                <dt>Jobs skipped</dt>
                <dd>{summary.jobs_skipped}</dd>
              </div>
            </dl>
            {summary.skipped.map((reason) => (
              <div className="attack-warning" key={reason}>
                <Icon name="activity" size={16} />
                <span>
                  <strong>Not restored</strong>
                  {reason}
                </span>
              </div>
            ))}
          </>
        ) : (
          <p className="score-hint">
            Replay rebuilds the in-memory index from this journal. Run evidence is always restored;
            a dataset or model handle is rebuilt only when the files on disk still hash to the
            recorded identity, and queued jobs from a dead process are never resurrected.
          </p>
        )}
      </section>

      <section className="panel">
        <JournalTable entries={entries} />
      </section>
    </div>
  );
}
