import { useEffect, useState } from "react";

import { Icon } from "../components/Icon";
import { formatDate, formatPercent } from "../format";
import type { LlmRedTeamRunRecord, ProbeCategory } from "../types";

const CATEGORY_LABEL: Record<ProbeCategory, string> = {
  system_prompt_leak: "System-prompt leak",
  instruction_override: "Instruction override",
  jailbreak: "Jailbreak framing",
};

export function LlmRedTeamPage({
  onOpenLlmRedTeam,
  runs,
}: {
  onOpenLlmRedTeam: () => void;
  runs: LlmRedTeamRunRecord[];
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => {
    if (runs.length && !runs.some((run) => run.id === selectedId)) {
      setSelectedId(runs[0].id);
    }
  }, [runs, selectedId]);
  const selected = runs.find((run) => run.id === selectedId) ?? runs[0] ?? null;

  return (
    <div className="page-content">
      <section className="registry-summary">
        <div>
          <span className="summary-icon">
            <Icon name="terminal" size={26} />
          </span>
          <div>
            <h2>LLM prompt-injection red-team</h2>
            <p>
              Probe an authorized LLM for system-prompt leaks, instruction overrides and jailbreak
              framings. Success means the model revealed a planted secret or followed an injected
              instruction — measured, not exploited.
            </p>
          </div>
        </div>
        <button className="button secondary compact" type="button" onClick={onOpenLlmRedTeam}>
          <Icon name="shield" size={15} /> Run red-team
        </button>
      </section>

      {runs.length ? (
        <div className="page-content split-layout">
          <section className="panel runs-panel">
            <div className="defense-table">
              <div className="defense-head llm-head">
                <span>Target</span>
                <span>Probes</span>
                <span>Injection rate</span>
                <span />
              </div>
              {runs.map((run) => (
                <button
                  className={`defense-row llm-row ${selectedId === run.id ? "selected" : ""}`}
                  key={run.id}
                  type="button"
                  onClick={() => setSelectedId(run.id)}
                >
                  <span className="attack-name">
                    <i>LLM</i>
                    <span>
                      <b>{run.target_host}</b>
                      <small>{formatDate(run.created_at)}</small>
                    </span>
                  </span>
                  <span className="mono">
                    {run.metrics.successful_probes}/{run.metrics.total_probes}
                  </span>
                  <strong
                    className={run.metrics.injection_success_rate > 0 ? "robust-value warn" : "robust-value"}
                  >
                    {formatPercent(run.metrics.injection_success_rate)}
                  </strong>
                  <Icon name="chevron" size={16} />
                </button>
              ))}
            </div>
          </section>

          <aside className="panel inspector">
            {selected ? (
              <>
                <div className="inspector-top">
                  <span className={selected.metrics.injection_success_rate > 0 ? "attack-status" : "sealed"}>
                    <Icon
                      name={selected.metrics.injection_success_rate > 0 ? "close" : "check"}
                      size={13}
                    />
                    {selected.metrics.injection_success_rate > 0 ? "Vulnerable" : "Held"}
                  </span>
                  <span className="mono faint">{formatDate(selected.created_at)}</span>
                </div>
                <h2>{selected.target_host}</h2>
                <p>
                  {selected.metrics.successful_probes} of {selected.metrics.total_probes} probes
                  succeeded ·{" "}
                  {selected.config.retain_text ? "text retained" : "text redacted"}
                </p>

                <div className="metric-pairs">
                  {Object.entries(selected.metrics.by_category).map(([category, count]) => (
                    <span key={category}>
                      <small>{CATEGORY_LABEL[category as ProbeCategory] ?? category}</small>
                      <b>{count} hit</b>
                    </span>
                  ))}
                </div>

                <div className="probe-list">
                  {selected.probes.map((probe) => (
                    <div className={`probe-row ${probe.succeeded ? "hit" : "clean"}`} key={probe.probe_id}>
                      <Icon name={probe.succeeded ? "close" : "check"} size={13} />
                      <span>
                        <b>{probe.probe_id}</b>
                        <small>{probe.detail}</small>
                      </span>
                    </div>
                  ))}
                </div>

                {selected.warnings.map((warning) => (
                  <small className="inspector-footnote" key={warning}>
                    {warning}
                  </small>
                ))}
              </>
            ) : null}
          </aside>
        </div>
      ) : (
        <section className="panel">
          <div className="empty-panel">
            <span className="empty-icon">
              <Icon name="terminal" size={22} />
            </span>
            <h3>No LLM red-team runs yet</h3>
            <p>
              Point AIShield at an LLM you are authorized to test. Set
              <code> AISHIELD_LLM_TARGETS_ALLOWLIST</code> on the server first — an empty allowlist
              refuses every target.
            </p>
            <button className="button primary compact" type="button" onClick={onOpenLlmRedTeam}>
              Configure a target
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
