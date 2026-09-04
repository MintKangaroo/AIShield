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
            <h2>Append-only 메타데이터 저널</h2>
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
            <span className="kicker">재시작 복구</span>
            <h3>저널 재생</h3>
          </div>
          <button
            className="button secondary compact"
            disabled={busy || !entries.length}
            type="button"
            onClick={onReplay}
          >
            <Icon name="refresh" size={15} />
            {busy ? "재생 중…" : "저널 재생"}
          </button>
        </div>
        {summary ? (
          <>
            <dl className="score-facts replay-facts">
              <div>
                <dt>읽은 항목</dt>
                <dd>{summary.entries_read}</dd>
              </div>
              <div>
                <dt>데이터셋</dt>
                <dd>{summary.datasets_restored}</dd>
              </div>
              <div>
                <dt>모델</dt>
                <dd>{summary.models_restored}</dd>
              </div>
              <div>
                <dt>실행</dt>
                <dd>
                  {summary.baselines_restored +
                    summary.attacks_restored +
                    summary.defenses_restored +
                    summary.transfers_restored +
                    summary.training_restored}
                </dd>
              </div>
              <div>
                <dt>건너뛴 작업</dt>
                <dd>{summary.jobs_skipped}</dd>
              </div>
            </dl>
            {summary.skipped.map((reason) => (
              <div className="attack-warning" key={reason}>
                <Icon name="activity" size={16} />
                <span>
                  <strong>복구 안 됨</strong>
                  {reason}
                </span>
              </div>
            ))}
          </>
        ) : (
          <p className="score-hint">
            재생은 이 저널에서 메모리 인덱스를 재구성합니다. 실행 증거는 항상 복구되고, 데이터셋·모델 핸들은 디스크 파일 해시가 기록된 정체성과 일치할 때만 재구성되며, 죽은 프로세스의 큐잉된 작업은 되살리지 않습니다.
          </p>
        )}
      </section>

      <section className="panel">
        <JournalTable entries={entries} />
      </section>
    </div>
  );
}
