"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import { Application } from "@/lib/types";
import Navbar from "@/components/Navbar";

// ── Constants ─────────────────────────────────────────────────────────────────

const STATUSES = ["saved", "applied", "test", "interview", "rejected", "accepted"] as const;
type Status = typeof STATUSES[number];

const STATUS_META: Record<Status, { label: string; color: string; bg: string; dot: string }> = {
  saved:     { label: "Saved",     color: "text-slate-600",  bg: "bg-slate-100",   dot: "bg-slate-400" },
  applied:   { label: "Applied",   color: "text-blue-700",   bg: "bg-blue-100",    dot: "bg-blue-500" },
  test:      { label: "Test",      color: "text-purple-700", bg: "bg-purple-100",  dot: "bg-purple-500" },
  interview: { label: "Interview", color: "text-amber-700",  bg: "bg-amber-100",   dot: "bg-amber-500" },
  rejected:  { label: "Rejected",  color: "text-red-700",    bg: "bg-red-100",     dot: "bg-red-500" },
  accepted:  { label: "Accepted",  color: "text-green-700",  bg: "bg-green-100",   dot: "bg-green-500" },
};

type ViewMode = "table" | "kanban";
type SortKey = "title" | "company" | "status" | "deadline" | "created_at" | "match_score";

// ── Export helpers ─────────────────────────────────────────────────────────────

function toCSV(applications: Application[]): string {
  const headers = ["Title", "Company", "Location", "Status", "Match Score", "Stipend", "Duration", "Deadline", "Platform", "Apply URL", "Notes", "Saved On"];
  const rows = applications.map((a) => [
    a.listing.title,
    a.listing.company,
    a.listing.location ?? "",
    a.status,
    a.match_score != null ? (a.match_score * 100).toFixed(0) + "%" : "",
    a.listing.stipend ?? "",
    a.listing.duration ?? "",
    a.listing.deadline ? new Date(a.listing.deadline).toLocaleDateString() : "",
    a.listing.source_platform,
    a.listing.apply_url,
    a.notes ?? "",
    new Date(a.created_at).toLocaleDateString(),
  ]);
  return [headers, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
    .join("\n");
}

function downloadCSV(content: string, filename: string) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadJSON(applications: Application[], filename: string) {
  const data = applications.map((a) => ({
    title: a.listing.title,
    company: a.listing.company,
    location: a.listing.location,
    status: a.status,
    match_score: a.match_score,
    stipend: a.listing.stipend,
    duration: a.listing.duration,
    deadline: a.listing.deadline,
    platform: a.listing.source_platform,
    apply_url: a.listing.apply_url,
    notes: a.notes,
    saved_on: a.created_at,
  }));
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Subcomponents ─────────────────────────────────────────────────────────────

function StatusBadge({ status, onChange }: { status: Status; onChange: (s: Status) => void }) {
  const meta = STATUS_META[status];
  return (
    <select
      value={status}
      onChange={(e) => onChange(e.target.value as Status)}
      className={`text-xs font-semibold px-2 py-1 rounded-full border-0 cursor-pointer focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-blue-400 ${meta.color} ${meta.bg}`}
    >
      {STATUSES.map((s) => (
        <option key={s} value={s}>{STATUS_META[s].label}</option>
      ))}
    </select>
  );
}

function DeadlineBadge({ deadline }: { deadline: string | null }) {
  if (!deadline) return <span className="text-slate-300 text-xs">—</span>;
  const days = Math.ceil((new Date(deadline).getTime() - Date.now()) / 86400000);
  const label = days < 0 ? "Passed" : days === 0 ? "Today!" : days === 1 ? "Tomorrow" : `${days}d`;
  const cls = days < 0 ? "text-slate-400" : days <= 1 ? "text-red-600 font-semibold" : days <= 3 ? "text-orange-500 font-medium" : "text-slate-500";
  return <span className={`text-xs ${cls}`}>{label}</span>;
}

function MatchBar({ score }: { score: number | null }) {
  if (score == null) return <span className="text-slate-300 text-xs">—</span>;
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? "bg-green-500" : pct >= 40 ? "bg-yellow-400" : "bg-slate-300";
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-500">{pct}%</span>
    </div>
  );
}

// ── Inline editable notes cell ────────────────────────────────────────────────

function NotesCell({ value, onSave }: { value: string | null; onSave: (v: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value ?? "");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { if (editing) ref.current?.focus(); }, [editing]);

  function commit() {
    setEditing(false);
    if (text !== (value ?? "")) onSave(text);
  }

  if (editing) {
    return (
      <textarea
        ref={ref}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => { if (e.key === "Escape") { setEditing(false); setText(value ?? ""); } }}
        rows={2}
        className="w-full text-xs border border-blue-300 rounded px-2 py-1 focus:outline-none resize-none"
      />
    );
  }
  return (
    <span
      onClick={() => setEditing(true)}
      className="text-xs text-slate-500 cursor-pointer hover:text-blue-600 block min-h-[1.5rem] group"
      title="Click to edit"
    >
      {value || <span className="text-slate-300 group-hover:text-blue-300">+ add note</span>}
    </span>
  );
}

// ── Kanban column ─────────────────────────────────────────────────────────────

function KanbanColumn({
  status, apps, onStatusChange, onDelete,
}: {
  status: Status;
  apps: Application[];
  onStatusChange: (id: string, s: Status) => void;
  onDelete: (id: string) => void;
}) {
  const meta = STATUS_META[status];
  return (
    <div className="flex-1 min-w-[200px] max-w-[260px]">
      <div className={`flex items-center gap-2 mb-3 px-3 py-2 rounded-lg ${meta.bg}`}>
        <span className={`w-2 h-2 rounded-full ${meta.dot}`} />
        <span className={`text-sm font-semibold ${meta.color}`}>{meta.label}</span>
        <span className={`ml-auto text-xs font-bold ${meta.color}`}>{apps.length}</span>
      </div>
      <div className="space-y-2 min-h-[100px]">
        {apps.map((a) => (
          <div key={a.id} className="bg-white border border-slate-200 rounded-xl p-3 shadow-sm hover:shadow-md transition-shadow">
            <p className="font-semibold text-slate-800 text-sm leading-tight line-clamp-2">{a.listing.title}</p>
            <p className="text-slate-400 text-xs mt-1">{a.listing.company}</p>
            {a.listing.location && <p className="text-slate-400 text-xs">📍 {a.listing.location}</p>}
            {a.listing.stipend && <p className="text-slate-500 text-xs mt-1">💰 {a.listing.stipend}</p>}
            <div className="mt-2 flex items-center justify-between">
              <DeadlineBadge deadline={a.listing.deadline} />
              <MatchBar score={a.match_score} />
            </div>
            <div className="mt-2 pt-2 border-t border-slate-100 flex items-center justify-between gap-2">
              <select
                value={a.status}
                onChange={(e) => onStatusChange(a.id, e.target.value as Status)}
                className={`text-xs font-semibold px-2 py-0.5 rounded-full border-0 cursor-pointer ${meta.color} ${meta.bg}`}
              >
                {STATUSES.map((s) => <option key={s} value={s}>{STATUS_META[s].label}</option>)}
              </select>
              <div className="flex gap-1">
                <a href={a.listing.apply_url} target="_blank" rel="noopener noreferrer"
                  className="text-xs text-blue-500 hover:underline">Apply</a>
                <button onClick={() => onDelete(a.id)} className="text-xs text-slate-300 hover:text-red-400 ml-1">✕</button>
              </div>
            </div>
          </div>
        ))}
        {apps.length === 0 && (
          <div className="border-2 border-dashed border-slate-200 rounded-xl h-20 flex items-center justify-center">
            <span className="text-slate-300 text-xs">Empty</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function TrackerPage() {
  const router = useRouter();
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<ViewMode>("table");
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [filterStatus, setFilterStatus] = useState<Status | "all">("all");
  const [search, setSearch] = useState("");
  const [showExport, setShowExport] = useState(false);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace("/login"); return; }
    api.get("/applications")
      .then((r) => setApplications(r.data))
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  // ── Mutations ───────────────────────────────────────────────────────────────

  async function updateStatus(id: string, status: Status) {
    try {
      const r = await api.patch(`/applications/${id}`, { status });
      setApplications((prev) => prev.map((a) => a.id === id ? r.data : a));
    } catch {}
  }

  async function updateNotes(id: string, notes: string) {
    try {
      const r = await api.patch(`/applications/${id}`, { notes });
      setApplications((prev) => prev.map((a) => a.id === id ? r.data : a));
    } catch {}
  }

  async function deleteApp(id: string) {
    if (!confirm("Remove this internship from your tracker?")) return;
    try {
      await api.delete(`/applications/${id}`);
      setApplications((prev) => prev.filter((a) => a.id !== id));
    } catch {}
  }

  // ── Filter + sort ───────────────────────────────────────────────────────────

  const filtered = applications
    .filter((a) => filterStatus === "all" || a.status === filterStatus)
    .filter((a) => {
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        a.listing.title.toLowerCase().includes(q) ||
        a.listing.company.toLowerCase().includes(q) ||
        (a.listing.location ?? "").toLowerCase().includes(q)
      );
    })
    .sort((a, b) => {
      let av: any, bv: any;
      switch (sortKey) {
        case "title":       av = a.listing.title;    bv = b.listing.title; break;
        case "company":     av = a.listing.company;  bv = b.listing.company; break;
        case "status":      av = a.status;           bv = b.status; break;
        case "deadline":    av = a.listing.deadline ?? ""; bv = b.listing.deadline ?? ""; break;
        case "match_score": av = a.match_score ?? -1; bv = b.match_score ?? -1; break;
        default:            av = a.created_at;       bv = b.created_at;
      }
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
  }

  const SortIcon = ({ k }: { k: SortKey }) =>
    sortKey === k ? <span className="ml-1">{sortDir === "asc" ? "↑" : "↓"}</span> : null;

  // ── Stats ───────────────────────────────────────────────────────────────────

  const stats = STATUSES.reduce((acc, s) => {
    acc[s] = applications.filter((a) => a.status === s).length;
    return acc;
  }, {} as Record<Status, number>);

  // ── Export ──────────────────────────────────────────────────────────────────

  const exportDate = new Date().toISOString().slice(0, 10);

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 py-8">

        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Application Tracker</h2>
            <p className="text-slate-500 text-sm mt-1">{applications.length} internships tracked</p>
          </div>
          <div className="flex gap-2 flex-wrap">
            {/* View toggle */}
            <div className="flex bg-white border border-slate-200 rounded-lg overflow-hidden">
              <button onClick={() => setView("table")}
                className={`px-3 py-2 text-sm font-medium transition-colors ${view === "table" ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-50"}`}>
                ☰ Table
              </button>
              <button onClick={() => setView("kanban")}
                className={`px-3 py-2 text-sm font-medium transition-colors ${view === "kanban" ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-50"}`}>
                ⊞ Kanban
              </button>
            </div>

            {/* Export dropdown */}
            <div className="relative">
              <button onClick={() => setShowExport((s) => !s)}
                className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2">
                ↓ Export
              </button>
              {showExport && (
                <div className="absolute right-0 top-10 bg-white border border-slate-200 rounded-xl shadow-lg z-10 w-44 overflow-hidden">
                  <button onClick={() => { downloadCSV(toCSV(filtered), `internhub-tracker-${exportDate}.csv`); setShowExport(false); }}
                    className="w-full text-left px-4 py-3 text-sm text-slate-700 hover:bg-slate-50 border-b border-slate-100">
                    📊 Export as CSV
                  </button>
                  <button onClick={() => { downloadJSON(filtered, `internhub-tracker-${exportDate}.json`); setShowExport(false); }}
                    className="w-full text-left px-4 py-3 text-sm text-slate-700 hover:bg-slate-50">
                    📋 Export as JSON
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 mb-6">
          {STATUSES.map((s) => {
            const meta = STATUS_META[s];
            return (
              <button key={s}
                onClick={() => setFilterStatus(filterStatus === s ? "all" : s)}
                className={`rounded-xl p-3 text-center border-2 transition-all ${
                  filterStatus === s ? `${meta.bg} border-current ${meta.color}` : "bg-white border-transparent hover:border-slate-200"
                }`}>
                <p className={`text-2xl font-bold ${meta.color}`}>{stats[s]}</p>
                <p className="text-xs text-slate-500 mt-0.5">{meta.label}</p>
              </button>
            );
          })}
        </div>

        {/* Search + filter bar */}
        <div className="flex gap-3 mb-4 flex-wrap">
          <input
            value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by title, company or location…"
            className="flex-1 min-w-60 px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          />
          {filterStatus !== "all" && (
            <button onClick={() => setFilterStatus("all")}
              className="px-3 py-2 text-xs text-slate-500 border border-slate-300 rounded-lg hover:bg-slate-50">
              Clear filter ✕
            </button>
          )}
          <span className="text-sm text-slate-400 self-center">{filtered.length} shown</span>
        </div>

        {loading ? (
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-14 bg-white border border-slate-200 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-20 text-slate-400">
            <p className="text-4xl mb-3">📋</p>
            <p className="font-medium">No applications yet</p>
            <p className="text-sm mt-1">Save internships from the <a href="/dashboard" className="text-blue-500 hover:underline">dashboard</a> to track them here</p>
          </div>
        ) : view === "kanban" ? (

          /* ── Kanban view ──────────────────────────────────────────────────── */
          <div className="flex gap-3 overflow-x-auto pb-4">
            {STATUSES.map((s) => (
              <KanbanColumn
                key={s} status={s}
                apps={filtered.filter((a) => a.status === s)}
                onStatusChange={updateStatus}
                onDelete={deleteApp}
              />
            ))}
          </div>

        ) : (

          /* ── Table view ───────────────────────────────────────────────────── */
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    {[
                      { key: "title" as SortKey,       label: "Role" },
                      { key: "company" as SortKey,     label: "Company" },
                      { key: "status" as SortKey,      label: "Status" },
                      { key: "deadline" as SortKey,    label: "Deadline" },
                      { key: "match_score" as SortKey, label: "Match" },
                    ].map(({ key, label }) => (
                      <th key={key}
                        onClick={() => toggleSort(key)}
                        className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide cursor-pointer hover:text-slate-800 select-none whitespace-nowrap">
                        {label}<SortIcon k={key} />
                      </th>
                    ))}
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Notes</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Platform</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filtered.map((a) => {
                    const meta = STATUS_META[a.status as Status];
                    return (
                      <tr key={a.id} className="hover:bg-slate-50 transition-colors group">
                        {/* Role */}
                        <td className="px-4 py-3 max-w-[220px]">
                          <a href={a.listing.apply_url} target="_blank" rel="noopener noreferrer"
                            className="font-medium text-slate-800 hover:text-blue-600 hover:underline line-clamp-2 block">
                            {a.listing.title}
                          </a>
                          {a.listing.location && (
                            <span className="text-xs text-slate-400">📍 {a.listing.location}</span>
                          )}
                        </td>
                        {/* Company */}
                        <td className="px-4 py-3">
                          <span className="font-medium text-slate-700">{a.listing.company}</span>
                          {a.listing.stipend && (
                            <p className="text-xs text-slate-400">{a.listing.stipend}</p>
                          )}
                        </td>
                        {/* Status */}
                        <td className="px-4 py-3 whitespace-nowrap">
                          <StatusBadge status={a.status as Status} onChange={(s) => updateStatus(a.id, s)} />
                        </td>
                        {/* Deadline */}
                        <td className="px-4 py-3 whitespace-nowrap">
                          <DeadlineBadge deadline={a.listing.deadline} />
                          {a.listing.deadline && (
                            <p className="text-xs text-slate-400">
                              {new Date(a.listing.deadline).toLocaleDateString()}
                            </p>
                          )}
                        </td>
                        {/* Match */}
                        <td className="px-4 py-3">
                          <MatchBar score={a.match_score} />
                        </td>
                        {/* Notes */}
                        <td className="px-4 py-3 max-w-[200px]">
                          <NotesCell value={a.notes} onSave={(v) => updateNotes(a.id, v)} />
                        </td>
                        {/* Platform */}
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className={`text-xs font-medium px-2 py-1 rounded-full capitalize ${
                            a.listing.source_platform === "internshala" ? "bg-green-100 text-green-700" :
                            a.listing.source_platform === "linkedin"    ? "bg-blue-100 text-blue-700" :
                                                                          "bg-orange-100 text-orange-700"
                          }`}>
                            {a.listing.source_platform}
                          </span>
                        </td>
                        {/* Actions */}
                        <td className="px-4 py-3">
                          <button onClick={() => deleteApp(a.id)}
                            className="text-slate-800 hover:text-red-400 transition-colors cursor-pointer group-hover:opacity-100">
                            🗑
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
