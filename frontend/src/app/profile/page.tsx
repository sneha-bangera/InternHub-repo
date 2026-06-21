"use client";
import { useState, useEffect, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import { UserSkill, Application, User } from "@/lib/types";
import Navbar from "@/components/Navbar";

const PROFICIENCY = ["beginner", "intermediate", "advanced"] as const;
const STATUS_COLORS: Record<string, string> = {
  saved: "bg-slate-100 text-slate-600",
  applied: "bg-blue-100 text-blue-700",
  rejected: "bg-red-100 text-red-700",
  accepted: "bg-green-100 text-green-700",
};

export default function ProfilePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [skills, setSkills] = useState<UserSkill[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);

  // Skill form
  const [newSkill, setNewSkill] = useState("");
  const [proficiency, setProficiency] = useState<string>("intermediate");
  const [addingSkill, setAddingSkill] = useState(false);
  const [skillError, setSkillError] = useState("");

  // WhatsApp form
  const [waNumber, setWaNumber] = useState("");
  const [savingWa, setSavingWa] = useState(false);
  const [waMsg, setWaMsg] = useState("");

  // Reminder test
  const [testingReminder, setTestingReminder] = useState(false);
  const [reminderResult, setReminderResult] = useState<string>("");

  useEffect(() => {
    if (!isLoggedIn()) { router.replace("/login"); return; }
    Promise.all([
      api.get("/auth/me"),
      api.get("/user/skills"),
      api.get("/applications"),
    ]).then(([me, sk, apps]) => {
      setUser(me.data);
      setWaNumber(me.data.whatsapp_number || "");
      setSkills(sk.data);
      setApplications(apps.data);
    }).catch(() => router.replace("/login"));
  }, [router]);

  // ── Skills ────────────────────────────────────────────────────────────────
  async function addSkill(e: FormEvent) {
    e.preventDefault();
    if (!newSkill.trim()) return;
    setSkillError("");
    setAddingSkill(true);
    try {
      const r = await api.post("/user/skills", { skill: newSkill.trim(), proficiency });
      setSkills((prev) => {
        const exists = prev.find((s) => s.id === r.data.id);
        return exists ? prev.map((s) => s.id === r.data.id ? r.data : s) : [...prev, r.data];
      });
      setNewSkill("");
    } catch (err: any) {
      setSkillError(err?.response?.data?.detail || "Failed to add skill");
    } finally {
      setAddingSkill(false);
    }
  }

  async function removeSkill(id: string) {
    try {
      await api.delete(`/user/skills/${id}`);
      setSkills((prev) => prev.filter((s) => s.id !== id));
    } catch {}
  }

  // ── WhatsApp number ───────────────────────────────────────────────────────
  async function saveWhatsApp(e: FormEvent) {
    e.preventDefault();
    setSavingWa(true);
    setWaMsg("");
    try {
      // We update via a dedicated endpoint — for now patch through user skills
      // endpoint isn't wired; call a simple workaround using the existing /auth/me
      // We'll POST to /user/whatsapp which we add below, but for now store in state
      await api.patch("/user/whatsapp", { whatsapp_number: waNumber });
      setUser((u) => u ? { ...u, whatsapp_number: waNumber } : u);
      setWaMsg("✅ WhatsApp number saved!");
    } catch (err: any) {
      setWaMsg("❌ " + (err?.response?.data?.detail || "Failed to save number"));
    } finally {
      setSavingWa(false);
    }
  }

  // ── Test reminder ─────────────────────────────────────────────────────────
  async function testReminder() {
    setTestingReminder(true);
    setReminderResult("");
    try {
      const r = await api.post("/reminders/test");
      if (r.data.sent) {
        setReminderResult(`✅ WhatsApp sent to ${r.data.to}! Check your phone.`);
      } else if (r.data.message) {
        setReminderResult(`ℹ️ ${r.data.message}`);
      } else {
        setReminderResult("❌ Message not sent — check Twilio credentials in .env");
      }
    } catch (err: any) {
      setReminderResult("❌ " + (err?.response?.data?.detail || "Error"));
    } finally {
      setTestingReminder(false);
    }
  }

  // ── Applications ──────────────────────────────────────────────────────────
  async function updateAppStatus(id: string, status: string) {
    try {
      const r = await api.patch(`/applications/${id}`, { status });
      setApplications((prev) => prev.map((a) => a.id === id ? r.data : a));
    } catch {}
  }

  async function removeApp(id: string) {
    try {
      await api.delete(`/applications/${id}`);
      setApplications((prev) => prev.filter((a) => a.id !== id));
    } catch {}
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar />
      <main className="max-w-3xl mx-auto px-4 py-8 space-y-6">

        {/* ── User info ───────────────────────────────────────────────────── */}
        <section className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Your Profile</h2>
          {user && (
            <div className="space-y-2 text-sm">
              <div className="flex gap-3">
                <span className="text-slate-400 w-28">Name</span>
                <span className="font-medium text-slate-800">{user.full_name}</span>
              </div>
              <div className="flex gap-3">
                <span className="text-slate-400 w-28">Email</span>
                <span className="text-slate-800">{user.email}</span>
              </div>
              <div className="flex gap-3">
                <span className="text-slate-400 w-28">Member since</span>
                <span className="text-slate-800">{new Date(user.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          )}
        </section>

        {/* ── WhatsApp reminders ──────────────────────────────────────────── */}
        <section className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-1">WhatsApp Reminders</h2>
          <p className="text-slate-500 text-sm mb-4">
            Get notified when application deadlines are within 3 days.
          </p>

          <form onSubmit={saveWhatsApp} className="flex gap-2 mb-3 flex-wrap">
            <input
              type="tel" value={waNumber} onChange={(e) => setWaNumber(e.target.value)}
              placeholder="+919876543210"
              className="flex-1 min-w-48 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button type="submit" disabled={savingWa}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
              {savingWa ? "Saving…" : "Save Number"}
            </button>
          </form>

          {waMsg && <p className="text-sm mb-3">{waMsg}</p>}

          <button
            onClick={testReminder} disabled={testingReminder || !user?.whatsapp_number}
            className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {testingReminder ? "Sending…" : "Send Test Reminder Now"}
          </button>
          {!user?.whatsapp_number && (
            <p className="text-xs text-slate-400 mt-1">Save a WhatsApp number first to test reminders.</p>
          )}
          {reminderResult && (
            <p className="text-sm mt-3 p-3 bg-slate-50 rounded-lg border border-slate-200">{reminderResult}</p>
          )}
        </section>

        {/* ── Skills ──────────────────────────────────────────────────────── */}
        <section className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">
            Skills <span className="text-slate-400 font-normal text-sm">({skills.length})</span>
          </h2>

          <form onSubmit={addSkill} className="flex gap-2 mb-4 flex-wrap">
            <input
              value={newSkill} onChange={(e) => setNewSkill(e.target.value)}
              placeholder="e.g. Python, React, SQL…"
              className="flex-1 min-w-40 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <select value={proficiency} onChange={(e) => setProficiency(e.target.value)}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
              {PROFICIENCY.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <button type="submit" disabled={addingSkill || !newSkill.trim()}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
              {addingSkill ? "Adding…" : "+ Add"}
            </button>
          </form>
          {skillError && <p className="text-red-500 text-xs mb-3">{skillError}</p>}

          {skills.length === 0 ? (
            <p className="text-slate-400 text-sm">No skills yet. Add skills to get personalised match scores on the dashboard.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {skills.map((s) => (
                <div key={s.id} className="flex items-center gap-1.5 bg-slate-100 rounded-full px-3 py-1">
                  <span className="text-sm text-slate-700 font-medium">{s.skill}</span>
                  {s.proficiency && <span className="text-xs text-slate-400">· {s.proficiency}</span>}
                  <button onClick={() => removeSkill(s.id)}
                    className="text-slate-400 hover:text-red-500 transition-colors ml-1 text-xs">✕</button>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* ── Saved & Applied ─────────────────────────────────────────────── */}
        <section className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">
            Saved & Applied <span className="text-slate-400 font-normal text-sm">({applications.length})</span>
          </h2>

          {applications.length === 0 ? (
            <p className="text-slate-400 text-sm">No saved internships yet. Hit "Save" on any listing in the dashboard.</p>
          ) : (
            <div className="space-y-3">
              {applications.map((a) => {
                const deadline = a.listing.deadline ? new Date(a.listing.deadline) : null;
                const daysLeft = deadline ? Math.ceil((deadline.getTime() - Date.now()) / 86400000) : null;
                return (
                  <div key={a.id} className="flex items-start gap-3 p-3 rounded-lg border border-slate-100 hover:bg-slate-50 transition-colors">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-slate-800 text-sm truncate">{a.listing.title}</p>
                      <p className="text-slate-400 text-xs">{a.listing.company} · {a.listing.source_platform}</p>
                      {daysLeft !== null && (
                        <p className={`text-xs mt-0.5 font-medium ${daysLeft <= 1 ? "text-red-500" : daysLeft <= 3 ? "text-orange-500" : "text-slate-400"}`}>
                          {daysLeft <= 0 ? "Deadline passed" : daysLeft === 1 ? "Due tomorrow!" : `${daysLeft}d left`}
                          {daysLeft <= 3 && daysLeft > 0 && " 🔔"}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <select value={a.status} onChange={(e) => updateAppStatus(a.id, e.target.value)}
                        className={`text-xs font-medium px-2 py-1 rounded-full border-0 cursor-pointer focus:outline-none ${STATUS_COLORS[a.status]}`}>
                        <option value="saved">saved</option>
                        <option value="applied">applied</option>
                        <option value="rejected">rejected</option>
                        <option value="accepted">accepted</option>
                      </select>
                      <button onClick={() => removeApp(a.id)}
                        className="text-slate-300 hover:text-red-400 transition-colors text-sm">✕</button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

      </main>
    </div>
  );
}
