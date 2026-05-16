import { useMemo, useState } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/run-workflow";

const REMINDER_STAGES = ["initial", "first", "second", "third", "escalation"];
const STAGE_LABELS = {
  initial: "Initial Reminder",
  first: "1st Reminder",
  second: "2nd Reminder",
  third: "3rd Reminder",
  escalation: "Escalation",
};

// ─── Root ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [excelFile, setExcelFile] = useState(null);
  const [repliesFile, setRepliesFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("summary");

  const emailRows = useMemo(() => {
    if (!results?.final_actions) return [];
    return results.final_actions.filter(
      (r) => r.email_subject && r.email_body &&
        ["sent", "drafted_for_review"].includes(r.final_action)
    );
  }, [results]);

  async function handleRun() {
    if (!excelFile) { setError("Please upload the AR Excel file."); return; }
    setLoading(true); setError(""); setResults(null);
    try {
      const fd = new FormData();
      fd.append("excel_file", excelFile);
      if (repliesFile) fd.append("replies_file", repliesFile);
      const res = await fetch(API_URL, { method: "POST", body: fd });
      if (!res.ok) {
        let msg = `Server error (${res.status})`;
        try { const d = await res.json(); if (d?.detail) msg = typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail); } catch {}
        throw new Error(msg);
      }
      const data = await res.json();
      setResults(data);
      setActiveTab("summary");
    } catch (e) {
      setError(e.message || "Workflow failed.");
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setExcelFile(null); setRepliesFile(null); setResults(null);
    setError(""); setActiveTab("summary");
    ["excel-input", "replies-input"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = "";
    });
  }

  const tabs = [
    { id: "summary", label: "Summary" },
    { id: "stages", label: "Reminder Stages" },
    { id: "classification", label: "Response Classification" },
    { id: "final", label: "Final Actions" },
    { id: "emails", label: "Email Preview" },
    { id: "skipped", label: "Skipped Records" },
  ];

  return (
    <div className="app">
      <header className="hero">
        <span className="logo-badge">AR</span>
        <div>
          <h1>Collections Email Automation</h1>
          <p>Automated AR reminder workflow · FastAPI + Gemini AI</p>
        </div>
      </header>

      <main className="container">
        {/* Upload */}
        <section className="card upload-card">
          <h2>Upload Files</h2>
          <div className="upload-row">
            <FileBox id="excel-input" label="AR Excel File" accept=".xlsx,.xls" file={excelFile} required onChange={setExcelFile} />
            <FileBox id="replies-input" label="Customer Replies JSON" accept=".json" file={repliesFile} hint="Optional" onChange={setRepliesFile} />
          </div>
          <div className="btn-row">
            <button className="btn-primary" onClick={handleRun} disabled={loading}>
              {loading ? <><span className="spinner" /> Processing…</> : "Run Automation"}
            </button>
            <button className="btn-ghost" onClick={reset} disabled={loading}>Reset</button>
          </div>
          {error && <p className="error-msg">⚠ {error}</p>}
          {results?.summary?.reply_records_uploaded === 0 && (
            <p className="info-msg">ℹ No reply JSON uploaded — all eligible invoices treated as no_reply.</p>
          )}
        </section>

        {results && (
          <>
            {/* Tab nav */}
            <nav className="tab-nav">
              {tabs.map(t => (
                <button key={t.id} className={`tab-btn ${activeTab === t.id ? "active" : ""}`} onClick={() => setActiveTab(t.id)}>
                  {t.label}
                  {t.id === "skipped" && results.skipped_records?.length > 0 &&
                    <span className="badge red">{results.skipped_records.length}</span>}
                  {t.id === "classification" && results.response_classification?.length > 0 &&
                    <span className="badge blue">{results.response_classification.length}</span>}
                </button>
              ))}
            </nav>

            {/* Tab panels */}
            {activeTab === "summary" && <SummaryTab results={results} />}
            {activeTab === "stages" && <StagesTab results={results} />}
            {activeTab === "classification" && <ClassificationTab results={results} />}
            {activeTab === "final" && <FinalActionsTab results={results} />}
            {activeTab === "emails" && <EmailsTab results={results} emailRows={emailRows} />}
            {activeTab === "skipped" && <SkippedTab results={results} />}
          </>
        )}
      </main>
    </div>
  );
}

// ─── Tab: Summary ──────────────────────────────────────────────────────────────
function SummaryTab({ results }) {
  const s = results.summary || {};
  const counts = s.final_action_counts || {};

  return (
    <section className="card">
      <h2>Processing Summary</h2>

      {/* Assessment deliverable 1: Processing stats */}
      <div className="stat-grid">
        <Stat label="Raw Records" value={s.raw_records ?? 0} />
        <Stat label="Valid Overdue Invoices" value={s.valid_overdue_invoices ?? 0} color="blue" />
        <Stat label="Eligible for Reminder" value={s.eligible_reminders ?? 0} color="green" />
        <Stat label="Ignored (outside rules)" value={s.ignored_outside_reminder_rules ?? 0} color="orange" />
        <Stat label="Skipped Records" value={s.skipped_records ?? 0} color="red" />
        <Stat label="Reply Records Uploaded" value={s.reply_records_uploaded ?? 0} />
        <Stat label="Responses Processed" value={s.response_records_processed ?? 0} />
      </div>

      {/* Assessment deliverable: Final action counts */}
      <h3 style={{ marginTop: 24 }}>Final Action Counts</h3>
      <div className="action-pills">
        {["sent", "drafted_for_review", "ignored"].map(a => (
          <div key={a} className={`action-pill ${a.replace("_", "-")}`}>
            <strong>{counts[a] ?? 0}</strong>
            <span>{ACTION_LABEL[a]}</span>
          </div>
        ))}
      </div>

      {/* Assessment deliverable 7f: Assumptions */}
      {results.assumptions?.length > 0 && (
        <>
          <h3 style={{ marginTop: 24 }}>Assumptions &amp; Notes</h3>
          <ul className="assumptions-list">
            {results.assumptions.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </>
      )}
    </section>
  );
}

// ─── Tab: Reminder Stages ──────────────────────────────────────────────────────
// Assessment deliverable: separate outputs for each reminder stage
function StagesTab({ results }) {
  const [activeStage, setActiveStage] = useState("initial");
  const stageData = results.stage_outputs || {};

  return (
    <section className="card">
      <h2>Reminder Stage Outputs</h2>
      <p className="muted-text">Separate eligibility list per reminder stage as required by the assessment.</p>

      <div className="stage-tabs">
        {REMINDER_STAGES.map(s => {
          const count = stageData[s]?.length ?? 0;
          return (
            <button key={s} className={`stage-btn ${activeStage === s ? "active" : ""}`} onClick={() => setActiveStage(s)}>
              {STAGE_LABELS[s]} <span className="badge">{count}</span>
            </button>
          );
        })}
      </div>

      <div style={{ marginTop: 16 }}>
        {(stageData[activeStage]?.length > 0) ? (
          <>
            <div className="table-actions">
              <span className="muted-text">{stageData[activeStage].length} invoice(s) at {STAGE_LABELS[activeStage]}</span>
              <button className="btn-ghost small" onClick={() => downloadCSV(stageData[activeStage], `stage_${activeStage}.csv`)}>
                ↓ Download CSV
              </button>
            </div>
            <DataTable
              rows={stageData[activeStage]}
              columns={["document_number", "customer_name", "customer_email", "invoice_amount", "due_date", "aging_days"]}
            />
          </>
        ) : (
          <p className="muted-text">No invoices at this stage.</p>
        )}
      </div>
    </section>
  );
}

// ─── Tab: Response Classification ─────────────────────────────────────────────
// Assessment deliverable: response classification and summary for invoices with replies
function ClassificationTab({ results }) {
  const rows = results.response_classification || [];
  const withReplies = rows.filter(r => r.has_reply);
  const noReplies = rows.filter(r => !r.has_reply);

  return (
    <section className="card">
      <h2>Response Classification</h2>
      <p className="muted-text">AI-classified customer replies with key reason, promised date, and requested action.</p>

      {rows.length === 0 ? (
        <p className="muted-text">No response records — only eligible invoices are processed.</p>
      ) : (
        <>
          <div className="classification-summary">
            <span className="badge blue">{withReplies.length} with reply</span>
            <span className="badge gray">{noReplies.length} no reply</span>
          </div>

          <div className="table-actions">
            <button className="btn-ghost small" onClick={() => downloadCSV(rows, "response_classification.csv")}>↓ Download CSV</button>
          </div>

          <DataTable
            rows={rows}
            columns={[
              "document_number", "customer_name", "has_reply",
              "classification", "summary", "key_reason",
              "promised_payment_date", "requested_action",
              "human_review_required", "confidence",
            ]}
            cellRenderer={(col, val) => {
              if (col === "has_reply") return val ? <span className="badge green">Yes</span> : <span className="badge gray">No</span>;
              if (col === "human_review_required") return val === true || val === "true" ? <span className="badge orange">Yes</span> : <span className="badge green">No</span>;
              if (col === "classification") return <ClassBadge val={val} />;
              return String(val ?? "");
            }}
          />
        </>
      )}
    </section>
  );
}

// ─── Tab: Final Actions ────────────────────────────────────────────────────────
// Assessment deliverable: final action for each invoice (sent / drafted / ignored)
function FinalActionsTab({ results }) {
  const rows = results.final_actions || [];
  const [filter, setFilter] = useState("all");

  const filtered = filter === "all" ? rows : rows.filter(r => r.final_action === filter);

  return (
    <section className="card">
      <h2>Final Actions</h2>
      <p className="muted-text">Each invoice shows its final status: sent, drafted for review, or ignored.</p>

      <div className="filter-row">
        {["all", "sent", "drafted_for_review", "ignored"].map(f => (
          <button key={f} className={`filter-btn ${filter === f ? "active" : ""}`} onClick={() => setFilter(f)}>
            {f === "all" ? "All" : ACTION_LABEL[f]}
            <span className="badge">{f === "all" ? rows.length : rows.filter(r => r.final_action === f).length}</span>
          </button>
        ))}
      </div>

      <div className="table-actions">
        <button className="btn-ghost small" onClick={() => downloadCSV(rows, "final_actions.csv")}>↓ Download All CSV</button>
        <button className="btn-ghost small" onClick={() => downloadCSV(results.reminder_eligibility, "reminder_eligibility.csv")}>↓ Eligibility CSV</button>
      </div>

      <DataTable
        rows={filtered}
        columns={[
          "document_number", "customer_name", "invoice_amount", "due_date",
          "aging_days", "reminder_stage_label", "classification",
          "human_review_required", "final_action", "action_reason",
        ]}
        cellRenderer={(col, val) => {
          if (col === "final_action") return <ActionBadge val={val} />;
          if (col === "human_review_required") return val === true || val === "true" ? <span className="badge orange">Yes</span> : <span className="badge green">No</span>;
          if (col === "classification") return <ClassBadge val={val} />;
          return String(val ?? "");
        }}
      />
    </section>
  );
}

// ─── Tab: Email Preview ────────────────────────────────────────────────────────
// Assessment deliverable: sample normal + escalation email, plus browsable list
function EmailsTab({ results, emailRows }) {
  const [selected, setSelected] = useState(null);

  return (
    <section className="card">
      <h2>Email Preview</h2>

      {/* Assessment deliverable: sample normal and escalation emails */}
      <div className="sample-email-grid">
        <SampleEmailCard title="Sample Normal Reminder" email={results.sample_normal_email} />
        <SampleEmailCard title="Sample Escalation Email" email={results.sample_escalation_email} highlight />
      </div>

      <hr className="divider" />
      <h3>Browse All Generated Emails</h3>
      <p className="muted-text">{emailRows.length} email(s) generated for eligible invoices.</p>

      {emailRows.length > 0 ? (
        <>
          <select className="select" defaultValue="" onChange={e => {
            setSelected(emailRows.find(r => r.document_number === e.target.value) || null);
          }}>
            <option value="" disabled>Select an invoice to preview its email…</option>
            {emailRows.map(r => (
              <option key={r.document_number} value={r.document_number}>
                {r.document_number} · {r.customer_name} · {ACTION_LABEL[r.final_action] ?? r.final_action}
              </option>
            ))}
          </select>
          {selected && <EmailCard invoice={selected} />}
        </>
      ) : (
        <p className="muted-text">No emails generated.</p>
      )}
    </section>
  );
}

// ─── Tab: Skipped ──────────────────────────────────────────────────────────────
function SkippedTab({ results }) {
  const rows = results.skipped_records || [];
  return (
    <section className="card">
      <h2>Skipped Records</h2>
      <p className="muted-text">Records excluded during preprocessing (non-invoice types, missing data, duplicates, zero aging).</p>
      {rows.length === 0
        ? <p className="success-msg">✓ No skipped records.</p>
        : <DataTable rows={rows} columns={["row_number", "document_number", "reason"]} />}
    </section>
  );
}

// ─── Small components ──────────────────────────────────────────────────────────
function FileBox({ id, label, accept, file, hint, required, onChange }) {
  return (
    <div className="file-box">
      <label htmlFor={id}>
        {label} {required && <span className="req">*</span>} {hint && <span className="hint">({hint})</span>}
      </label>
      <input id={id} type="file" accept={accept} onChange={e => onChange(e.target.files?.[0] || null)} />
      <p className={file ? "file-name" : "muted-text"}>{file ? file.name : "No file selected"}</p>
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div className={`stat-card ${color ?? ""}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function SampleEmailCard({ title, email, highlight }) {
  if (!email?.email_subject) return (
    <div className={`email-sample-card empty ${highlight ? "escalation" : ""}`}>
      <h4>{title}</h4>
      <p className="muted-text">Not available.</p>
    </div>
  );
  return (
    <div className={`email-sample-card ${highlight ? "escalation" : ""}`}>
      <h4>{title}</h4>
      <EmailCard invoice={{ customer_email: "customer@example.com", ...email }} compact />
    </div>
  );
}

function EmailCard({ invoice, compact }) {
  function copy() {
    navigator.clipboard.writeText(`To: ${invoice.customer_email}\nSubject: ${invoice.email_subject}\n\n${invoice.email_body}`);
    alert("Email copied to clipboard.");
  }
  return (
    <div className="email-card">
      <div className="email-meta">
        <span><strong>To:</strong> {invoice.customer_email}</span>
        {invoice.reminder_stage_label && <span><strong>Stage:</strong> {invoice.reminder_stage_label}</span>}
        {invoice.final_action && <ActionBadge val={invoice.final_action} />}
      </div>
      <div className="email-subject">{invoice.email_subject}</div>
      <textarea className={`email-body ${compact ? "compact" : ""}`} value={invoice.email_body} readOnly />
      <button className="btn-ghost small" onClick={copy}>Copy Email</button>
    </div>
  );
}

function DataTable({ rows, columns, cellRenderer }) {
  if (!rows?.length) return <p className="muted-text">No records.</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map(c => <th key={c}>{c.replace(/_/g, " ")}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map(c => (
                <td key={c}>
                  {cellRenderer ? cellRenderer(c, row[c]) : String(row[c] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ClassBadge({ val }) {
  const colors = {
    payment_made: "green", payment_promised: "blue", dispute: "red",
    copy_request: "orange", ooo_bounce: "gray", no_meaningful: "gray", no_reply: "gray",
  };
  return <span className={`badge ${colors[val] ?? "gray"}`}>{val?.replace(/_/g, " ")}</span>;
}

function ActionBadge({ val }) {
  const colors = { sent: "green", drafted_for_review: "orange", ignored: "gray" };
  return <span className={`badge ${colors[val] ?? "gray"}`}>{ACTION_LABEL[val] ?? val}</span>;
}

// ─── Utils ─────────────────────────────────────────────────────────────────────
const ACTION_LABEL = {
  sent: "Sent",
  drafted_for_review: "Draft for Review",
  ignored: "Ignored",
};

function downloadCSV(rows, fileName) {
  if (!rows?.length) return;
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(","), ...rows.map(row =>
    headers.map(h => `"${String(row[h] ?? "").replaceAll('"', '""')}"`).join(",")
  )];
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  Object.assign(document.createElement("a"), { href: url, download: fileName }).click();
  URL.revokeObjectURL(url);
}