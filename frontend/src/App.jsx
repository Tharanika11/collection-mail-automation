import { useState } from "react";
import "./App.css";

const API_URL = "http://localhost:8000/run-workflow";

export default function App() {
  const [excelFile, setExcelFile] = useState(null);
  const [repliesFile, setRepliesFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");
  const [selectedInvoice, setSelectedInvoice] = useState(null);

  async function handleRunWorkflow() {
    if (!excelFile) {
      setError("Please upload the Excel file.");
      return;
    }

    setLoading(true);
    setError("");
    setResults(null);
    setSelectedInvoice(null);

    try {
      const formData = new FormData();
      formData.append("excel_file", excelFile);

      if (repliesFile) {
        formData.append("replies_file", repliesFile);
      }

      const response = await fetch(API_URL, {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        throw new Error("Backend processing failed.");
      }

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  function downloadCSV(rows, fileName) {
    if (!rows || rows.length === 0) return;

    const headers = Object.keys(rows[0]);
    const csvRows = [];

    csvRows.push(headers.join(","));

    rows.forEach((row) => {
      const values = headers.map((header) => {
        const value = row[header] ?? "";
        const escaped = String(value).replaceAll('"', '""');
        return `"${escaped}"`;
      });

      csvRows.push(values.join(","));
    });

    const csvContent = csvRows.join("\n");
    const blob = new Blob([csvContent], {
      type: "text/csv;charset=utf-8;"
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = fileName;
    link.click();

    URL.revokeObjectURL(url);
  }

  const emailRows =
    results?.final_actions?.filter((row) => row.should_generate_email) || [];

  return (
    <div className="app">
      <header className="hero">
        <div className="logo">AR</div>

        <div>
          <h1>Collections Email Automation</h1>
          <p>React + FastAPI UI for rule-based AR reminder workflow</p>
        </div>
      </header>

      <main className="container">
        <section className="card">
          <h2>1. Upload Files</h2>

          <div className="upload-grid">
            <div className="upload-box">
              <label>AR Excel File</label>
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={(event) => setExcelFile(event.target.files[0])}
              />

              {excelFile && <p className="file-name">{excelFile.name}</p>}
            </div>

            <div className="upload-box">
              <label>Customer Replies JSON Optional</label>
              <input
                type="file"
                accept=".json"
                onChange={(event) => setRepliesFile(event.target.files[0])}
              />

              {repliesFile && <p className="file-name">{repliesFile.name}</p>}
            </div>
          </div>

          <button
            className="primary-btn"
            onClick={handleRunWorkflow}
            disabled={loading}
          >
            {loading ? "Processing..." : "Run Automation"}
          </button>

          {error && <p className="error">{error}</p>}
        </section>

        {results && (
          <>
            <section className="card">
              <h2>2. Processing Summary</h2>

              <div className="stats-grid">
                <StatCard
                  label="Total Records"
                  value={results.summary.total_records}
                />

                <StatCard
                  label="Valid Invoices"
                  value={results.summary.valid_invoices}
                />

                <StatCard
                  label="Skipped Records"
                  value={results.summary.skipped_records}
                />

                <StatCard
                  label="Eligible Reminders"
                  value={results.summary.eligible_reminders}
                />

                <StatCard
                  label="Sample Replies"
                  value={results.summary.sample_replies}
                />
              </div>
            </section>

            <section className="card">
              <h2>3. Final Actions</h2>

              <div className="actions-row">
                <button
                  className="secondary-btn"
                  onClick={() =>
                    downloadCSV(results.reminder_eligibility, "reminder_eligibility.csv")
                  }
                >
                  Download Reminder CSV
                </button>

                <button
                  className="secondary-btn"
                  onClick={() =>
                    downloadCSV(results.response_classification, "response_classification.csv")
                  }
                >
                  Download Classification CSV
                </button>

                <button
                  className="secondary-btn"
                  onClick={() =>
                    downloadCSV(results.final_actions, "final_actions.csv")
                  }
                >
                  Download Final Actions CSV
                </button>
              </div>

              <DataTable
                rows={results.final_actions}
                columns={[
                  "document_number",
                  "customer_name",
                  "invoice_amount",
                  "due_date",
                  "aging_days",
                  "reminder_stage_label",
                  "classification",
                  "final_action"
                ]}
                onRowClick={(row) => setSelectedInvoice(row)}
              />
            </section>

            <section className="card">
              <h2>4. Skipped Records</h2>

              {results.skipped_records.length === 0 ? (
                <p className="success">No skipped records.</p>
              ) : (
                <DataTable
                  rows={results.skipped_records}
                  columns={["row_number", "document_number", "reason"]}
                />
              )}
            </section>

            <section className="card">
              <h2>5. Generated Email Preview</h2>

              {emailRows.length === 0 ? (
                <p>No generated emails found.</p>
              ) : (
                <>
                  <select
                    className="select"
                    onChange={(event) => {
                      const row = emailRows.find(
                        (item) => item.document_number === event.target.value
                      );

                      setSelectedInvoice(row);
                    }}
                    defaultValue=""
                  >
                    <option value="" disabled>
                      Select invoice
                    </option>

                    {emailRows.map((row) => (
                      <option key={row.document_number} value={row.document_number}>
                        {row.document_number} - {row.customer_name}
                      </option>
                    ))}
                  </select>

                  {selectedInvoice && selectedInvoice.email_subject && (
                    <EmailPreview invoice={selectedInvoice} />
                  )}
                </>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="stat-card">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function DataTable({ rows, columns, onRowClick }) {
  if (!rows || rows.length === 0) {
    return <p className="muted">No records found.</p>;
  }

  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>

        <tbody>
          {rows.map((row, index) => (
            <tr
              key={index}
              onClick={() => onRowClick && onRowClick(row)}
              className={onRowClick ? "clickable" : ""}
            >
              {columns.map((column) => (
                <td key={column}>{String(row[column] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EmailPreview({ invoice }) {
  function copyEmail() {
    const emailText = `To: ${invoice.customer_email}
Subject: ${invoice.email_subject}

${invoice.email_body}`;

    navigator.clipboard.writeText(emailText);
    alert("Email copied to clipboard.");
  }

  return (
    <div className="email-preview">
      <p>
        <strong>To:</strong> {invoice.customer_email}
      </p>

      <p>
        <strong>Subject:</strong> {invoice.email_subject}
      </p>

      <textarea value={invoice.email_body} readOnly />

      <button className="primary-btn" onClick={copyEmail}>
        Copy Email
      </button>
    </div>
  );
}