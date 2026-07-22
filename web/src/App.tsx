import { useEffect, useState } from "react";

type ApiState = "checking" | "ready" | "offline";

interface HealthResponse {
  status: "ok";
  version: string;
  compute_device: "cpu" | "cuda";
}

const foundations = [
  {
    marker: "01",
    title: "Reproducible runs",
    detail: "Dataset versions, model hashes, seeds, attack parameters, and environment snapshots.",
  },
  {
    marker: "02",
    title: "Paired evidence",
    detail: "Clean and robust accuracy travel together with raw, exportable metrics.",
  },
  {
    marker: "03",
    title: "Defense scrutiny",
    detail: "Transfer and adaptive attacks are first-class checks against gradient masking.",
  },
];

function App() {
  const [apiState, setApiState] = useState<ApiState>("checking");
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetch("/api/v1/health/live", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error("API health check failed");
        }
        return response.json() as Promise<HealthResponse>;
      })
      .then((payload) => {
        setHealth(payload);
        setApiState("ready");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setApiState("offline");
      });

    return () => controller.abort();
  }, []);

  const statusLabel =
    apiState === "ready"
      ? `API ${health?.version} · ${health?.compute_device.toUpperCase()}`
      : apiState === "checking"
        ? "Checking API"
        : "API offline";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#top" aria-label="AIShield home">
          <span className="brand-mark" aria-hidden="true">
            AS
          </span>
          <span>
            <strong>AIShield</strong>
            <small>Research Console</small>
          </span>
        </a>

        <nav aria-label="Primary navigation">
          <a className="nav-item active" href="#experiments">
            <span>Experiments</span>
            <span className="nav-count">0</span>
          </a>
          <a className="nav-item" href="#registry">
            Registry <span className="soon">Soon</span>
          </a>
          <a className="nav-item" href="#artifacts">
            Artifacts <span className="soon">Soon</span>
          </a>
        </nav>

        <div className="scope-note">
          <span>Release 01 scope</span>
          <strong>Image classification</strong>
          <p>PyTorch adversarial robustness on approved datasets.</p>
        </div>
      </aside>

      <main id="top">
        <header className="topbar">
          <div>
            <p className="eyebrow">Workspace / Overview</p>
            <h1>Robustness, with receipts.</h1>
          </div>
          <span className={`api-status ${apiState}`}>
            <i aria-hidden="true" /> {statusLabel}
          </span>
        </header>

        <section className="intro" aria-labelledby="intro-title">
          <div>
            <p className="section-label">Foundation ready</p>
            <h2 id="intro-title">Measure what survives the attack.</h2>
            <p>
              AIShield keeps model behavior, attack conditions, and evidence in one reproducible
              experiment record. Attack execution arrives in the next milestones.
            </p>
          </div>
          <div className="scope-tags" aria-label="Supported foundation capabilities">
            <span>CPU default</span>
            <span>GPU profile</span>
            <span>Schema v1.0</span>
          </div>
        </section>

        <section className="foundation-grid" aria-label="Research principles">
          {foundations.map((item) => (
            <article className="foundation-card" key={item.marker}>
              <span className="card-marker">{item.marker}</span>
              <h3>{item.title}</h3>
              <p>{item.detail}</p>
            </article>
          ))}
        </section>

        <section className="experiments" id="experiments" aria-labelledby="experiments-title">
          <div className="section-heading">
            <div>
              <p className="section-label">Experiment ledger</p>
              <h2 id="experiments-title">Recent experiments</h2>
            </div>
            <button type="button" disabled title="Available after the registry milestone">
              New experiment
            </button>
          </div>

          <div className="table-frame">
            <div className="table-header" aria-hidden="true">
              <span>Experiment</span>
              <span>Model / Dataset</span>
              <span>Clean</span>
              <span>Robust</span>
              <span>Status</span>
            </div>
            <div className="empty-state">
              <span className="empty-glyph" aria-hidden="true">
                ∅
              </span>
              <h3>No experiments recorded</h3>
              <p>The model and dataset registry will unlock experiment creation in stage 2.</p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
