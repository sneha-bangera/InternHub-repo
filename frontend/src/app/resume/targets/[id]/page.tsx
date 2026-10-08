"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, BriefcaseBusiness, Save } from "lucide-react";
import Navbar from "@/components/Navbar";
import { api, getApiErrorMessage } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import { JobTarget } from "@/lib/types";

export default function ResumeTargetPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const targetId = params.id;
  const [target, setTarget] = useState<JobTarget | null>(null);
  const [roleTitle, setRoleTitle] = useState("");
  const [seniority, setSeniority] = useState("");
  const [requiredSkills, setRequiredSkills] = useState("");
  const [preferredSkills, setPreferredSkills] = useState("");
  const [keywords, setKeywords] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    api.get<JobTarget>(`/api/resume/targets/${targetId}`)
      .then(({ data }) => {
        setTarget(data);
        setRoleTitle(data.role_title ?? "");
        setSeniority(data.seniority ?? "");
        setRequiredSkills(data.required_skills.join("\n"));
        setPreferredSkills(data.preferred_skills.join("\n"));
        setKeywords(data.keywords.join("\n"));
      })
      .catch((requestError: unknown) => {
        setError(getApiErrorMessage(requestError, "Could not load this target."));
      })
      .finally(() => setLoading(false));
  }, [router, targetId]);

  async function saveTarget(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      const { data } = await api.patch<JobTarget>(`/api/resume/targets/${targetId}`, {
        role_title: roleTitle.trim() || null,
        seniority: seniority.trim() || null,
        required_skills: requiredSkills.split("\n").map((item) => item.trim()).filter(Boolean),
        preferred_skills: preferredSkills.split("\n").map((item) => item.trim()).filter(Boolean),
        keywords: keywords.split("\n").map((item) => item.trim()).filter(Boolean),
      });
      setTarget(data);
      setSaved(true);
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, "Could not save target edits."));
    } finally {
      setSaving(false);
    }
  }

  const listFields = [
    {
      title: "Required skills",
      value: requiredSkills,
      setValue: setRequiredSkills,
      description: "Skills explicitly required for the role.",
    },
    {
      title: "Preferred skills",
      value: preferredSkills,
      setValue: setPreferredSkills,
      description: "Nice-to-have skills mentioned in the description.",
    },
    {
      title: "Keywords",
      value: keywords,
      setValue: setKeywords,
      description: "Terms to emphasize in your resume for this target.",
    },
  ];

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar />
      <main className="mx-auto max-w-4xl space-y-6 px-4 py-8">
        <Link href="/resume/targets/new" className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-blue-600">
          <ArrowLeft size={16} />
          New target
        </Link>

        {loading ? (
          <div role="status" className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
            Loading parsed job target…
          </div>
        ) : target ? (
          <>
            <header className="rounded-xl border border-slate-200 bg-white p-6">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-blue-50 p-2 text-blue-600"><BriefcaseBusiness size={20} /></div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-500">{target.company_name}</p>
                  <h1 className="mt-1 text-2xl font-bold text-slate-900">
                    {target.role_title || "Parsed job target"}
                  </h1>
                  {target.seniority && <p className="mt-2 text-sm text-slate-600">Seniority: {target.seniority}</p>}
                </div>
                <span className="hidden rounded-full bg-green-50 px-3 py-1 text-xs font-semibold text-green-700 sm:block">
                  JD parsed
                </span>
              </div>
            </header>

            {error && (
              <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}
            {saved && (
              <div role="status" className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
                Target updates saved.
              </div>
            )}

            <form onSubmit={saveTarget} className="space-y-6">
              <section className="rounded-xl border border-slate-200 bg-white p-6">
                <h2 className="mb-4 text-lg font-semibold text-slate-900">Role details</h2>
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="space-y-1.5 text-sm font-medium text-slate-700">
                    <span>Role title</span>
                    <input
                      value={roleTitle}
                      onChange={(event) => setRoleTitle(event.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 font-normal focus:outline-none focus:ring-2 focus:ring-blue-300"
                    />
                  </label>
                  <label className="space-y-1.5 text-sm font-medium text-slate-700">
                    <span>Seniority</span>
                    <input
                      value={seniority}
                      onChange={(event) => setSeniority(event.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 font-normal focus:outline-none focus:ring-2 focus:ring-blue-300"
                    />
                  </label>
                </div>
              </section>

              {listFields.map((field) => (
                <section key={field.title} className="rounded-xl border border-slate-200 bg-white p-6">
                  <label className="block space-y-1.5 text-sm font-medium text-slate-700">
                    <span className="text-lg font-semibold text-slate-900">{field.title}</span>
                    <span className="block text-xs font-normal text-slate-500">{field.description} One item per line.</span>
                    <textarea
                      rows={4}
                      value={field.value}
                      onChange={(event) => { field.setValue(event.target.value); setSaved(false); }}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 font-normal focus:outline-none focus:ring-2 focus:ring-blue-300"
                    />
                  </label>
                </section>
              ))}

              <details className="rounded-xl border border-slate-200 bg-white p-6">
                <summary className="cursor-pointer text-sm font-semibold text-slate-700">Original job description</summary>
                <pre className="mt-4 whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-600">
                  {target.jd_text}
                </pre>
              </details>

              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-600 disabled:opacity-50"
              >
                <Save size={16} />
                {saving ? "Saving…" : "Save target"}
              </button>
            </form>
          </>
        ) : (
          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <h1 className="text-lg font-semibold text-slate-900">Target unavailable</h1>
            {error && <p role="alert" className="mt-2 text-sm text-red-600">{error}</p>}
          </div>
        )}
      </main>
    </div>
  );
}
