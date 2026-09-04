import { useState } from "react";

import type { JournalEntry } from "../types";
import { Icon } from "./Icon";

/** Read a display label out of an untyped journal record without assuming a shape. */
function entryLabel(record: Record<string, unknown>) {
  // An experiment envelope nests its identity under `experiment`; every other
  // record carries it at the top level.
  const nested = record.experiment as Record<string, unknown> | undefined;
  const rawId = typeof record.id === "string" ? record.id : nested?.id;
  const rawCreated =
    typeof record.created_at === "string" ? record.created_at : nested?.created_at;
  return {
    id: typeof rawId === "string" ? rawId.slice(0, 8) : "—",
    created: typeof rawCreated === "string" ? rawCreated : null,
  };
}

export function JournalTable({ entries }: { entries: JournalEntry[] }) {
  const [kind, setKind] = useState<string>("all");
  const [expanded, setExpanded] = useState<number | null>(null);

  if (!entries.length) {
    return (
      <div className="empty-panel">
        <span className="empty-icon">
          <Icon name="book" size={22} />
        </span>
        <h3>메타데이터 저널이 비어 있습니다</h3>
        <p>
          모든 데이터셋·모델·베이스라인·공격·방어·전이·학습 레코드는 클라이언트로 반환되기 전에 canonical JSON으로 여기에 append됩니다.
        </p>
      </div>
    );
  }

  const kinds = ["all", ...Array.from(new Set(entries.map((entry) => entry.kind))).sort()];
  const visible = entries
    .map((entry, index) => ({ entry, index }))
    .filter(({ entry }) => kind === "all" || entry.kind === kind);

  return (
    <>
      <div className="journal-filters" role="group" aria-label="레코드 종류별 저널 필터">
        {kinds.map((item) => (
          <button
            className={kind === item ? "active" : ""}
            key={item}
            type="button"
            onClick={() => setKind(item)}
          >
            {item}
            <b>
              {item === "all"
                ? entries.length
                : entries.filter((entry) => entry.kind === item).length}
            </b>
          </button>
        ))}
      </div>
      <div className="journal-table">
        <div className="journal-head">
          <span>#</span>
          <span>종류</span>
          <span>레코드 id</span>
          <span>기록 시각</span>
          <span />
        </div>
        {visible.map(({ entry, index }) => {
          const { id, created } = entryLabel(entry.record);
          const isOpen = expanded === index;
          return (
            <div className={`journal-entry ${isOpen ? "open" : ""}`} key={index}>
              <button
                aria-expanded={isOpen}
                className="journal-row"
                type="button"
                onClick={() => setExpanded(isOpen ? null : index)}
              >
                <span className="mono faint">{index + 1}</span>
                <span className={`journal-kind ${entry.kind}`}>{entry.kind}</span>
                <span className="mono">{id}</span>
                <span className="mono faint">{created ?? "—"}</span>
                <Icon name="chevron" size={15} />
              </button>
              {isOpen && (
                <pre className="journal-payload">{JSON.stringify(entry.record, null, 2)}</pre>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}
