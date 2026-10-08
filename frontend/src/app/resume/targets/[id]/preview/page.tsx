"use client";

import { DragEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Download,
  ExternalLink,
  FileText,
  GripVertical,
  RotateCcw,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { api, getApiErrorMessage } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import {
  JobTarget,
  KeywordCoverage,
  ResumeProject,
  ResumeCompileJob,
  ResumeSections,
  ResumeSelection,
} from "@/lib/types";

const DEFAULT_PROJECT_LIMIT = 4;
const INITIAL_SECTIONS: ResumeSections = {
  contact: true,
  education: true,
  projects: true,
  skills: true,
  certificates: true,
};
const ALIASES: Record<string, string> = {
  js: "javascript",
  k8s: "kubernetes",
  apis: "api",
};

interface WeightedKeyword {
  display: string;
  normalized: string;
  weight: number;
}

function normalizeToken(token: string): string {
  if (ALIASES[token]) return ALIASES[token];
  if (token.length > 4 && token.endsWith("ies")) return `${token.slice(0, -3)}y`;
  if (token.length > 4 && token.endsWith("ing")) {
    let stem = token.slice(0, -3);
    if (stem.length > 2 && stem.at(-1) === stem.at(-2)) stem = stem.slice(0, -1);
    return stem;
  }
  if (token.length > 3 && token.endsWith("ed")) {
    let stem = token.slice(0, -2);
    if (stem.length > 2 && stem.at(-1) === stem.at(-2)) stem = stem.slice(0, -1);
    return stem;
  }
  if (
    token.length > 3 &&
    token.endsWith("s") &&
    !["ss", "us", "is", "es"].some((suffix) => token.endsWith(suffix))
  ) {
    return token.slice(0, -1);
  }
  return ALIASES[token] ?? token;
}

function normalizeText(text: string): string {
  return (text.toLocaleLowerCase().match(/[\w+#.]+/gu) ?? [])
    .map(normalizeToken)
    .join(" ");
}

function getWeightedKeywords(target: JobTarget): WeightedKeyword[] {
  const candidates = [
    ...target.required_skills.map((display) => ({ display, weight: 2 })),
    ...target.preferred_skills.map((display) => ({ display, weight: 1 })),
    ...target.keywords.map((display) => ({ display, weight: 1 })),
  ];
  const unique = new Map<string, WeightedKeyword>();
  candidates.forEach(({ display: rawDisplay, weight }) => {
    const display = rawDisplay.trim();
    const normalized = normalizeText(display);
    if (!normalized) return;
    const current = unique.get(normalized);
    if (!current || weight > current.weight) {
      unique.set(normalized, { display, normalized, weight });
    }
  });
  return [...unique.values()];
}

function projectText(project: ResumeProject): string {
  return [project.title, ...project.tech_stack, ...project.bullets].filter(Boolean).join(" ");
}

function coverageFor(
  keywords: WeightedKeyword[],
  selectedProjects: ResumeProject[],
  skills: ResumeSelection["skills"],
  certificates: ResumeSelection["certificates"],
): KeywordCoverage {
  const content = [
    ...selectedProjects.map(projectText),
    ...skills.map(({ item }) => [item.name, item.category, item.proficiency].filter(Boolean).join(" ")),
    ...certificates.map(({ item }) => [item.name, item.issuer].filter(Boolean).join(" ")),
  ].map(normalizeText).join(" ");
  const matched = keywords.filter(({ normalized }) => ` ${content} `.includes(` ${normalized} `));
  const totalWeight = keywords.reduce((sum, keyword) => sum + keyword.weight, 0);
  const matchedWeight = matched.reduce((sum, keyword) => sum + keyword.weight, 0);
  return {
    score: totalWeight ? Number((matchedWeight / totalWeight).toFixed(4)) : 0,
    matched_keywords: matched.map(({ display }) => display),
    missing_keywords: keywords
      .filter((keyword) => !matched.includes(keyword))
      .map(({ display }) => display),
  };
}

function reorder<T>(items: T[], fromIndex: number, toIndex: number): T[] {
  const updated = [...items];
  const [moved] = updated.splice(fromIndex, 1);
  updated.splice(toIndex, 0, moved);
  return updated;
}

export default function ResumeSelectionPreviewPage() {
  const router = useRouter();
  const { id: targetId } = useParams<{ id: string }>();
  const [target, setTarget] = useState<JobTarget | null>(null);
  const [selection, setSelection] = useState<ResumeSelection | null>(null);
  const [selectedProjectIds, setSelectedProjectIds] = useState<string[]>([]);
  const [draggedProjectId, setDraggedProjectId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sections, setSections] = useState<ResumeSections>(INITIAL_SECTIONS);
  const [compileJob, setCompileJob] = useState<ResumeCompileJob | null>(null);
  const [pdfUrl, setPdfUrl] = useState("");
  const [compileError, setCompileError] = useState("");
  const [openingOverleaf, setOpeningOverleaf] = useState(false);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    Promise.all([
      api.get<JobTarget>(`/api/resume/targets/${targetId}`),
      api.post<ResumeSelection>(`/api/resume/targets/${targetId}/select`, null, {
        params: { top_n: 20 },
      }),
    ])
      .then(([targetResponse, selectionResponse]) => {
        setTarget(targetResponse.data);
        setSelection(selectionResponse.data);
        setSelectedProjectIds(
          selectionResponse.data.projects
            .slice(0, DEFAULT_PROJECT_LIMIT)
            .map(({ item }) => item.id),
        );
      })
      .catch((requestError: unknown) => {
        setError(getApiErrorMessage(requestError, "Could not load the selection preview."));
      })
      .finally(() => setLoading(false));
  }, [router, targetId]);

  const selectedProjects = useMemo(() => {
    if (!selection) return [];
    const projectsById = new Map(
      selection.projects.map(({ item }) => [item.id, item]),
    );
    return selectedProjectIds
      .map((projectId) => projectsById.get(projectId))
      .filter((project): project is ResumeProject => project !== undefined);
  }, [selection, selectedProjectIds]);

  const afterCoverage = useMemo(() => {
    if (!target || !selection) return null;
    return coverageFor(
      getWeightedKeywords(target),
      selectedProjects,
      selection.skills,
      selection.certificates,
    );
  }, [target, selection, selectedProjects]);

  useEffect(() => {
    if (loading || !selection) return;
    let active = true;
    let pollTimer: number | undefined;
    let previewObjectUrl = "";

    const debounceTimer = window.setTimeout(async () => {
      setPdfUrl("");
      setCompileError("");
      setCompileJob(null);
      try {
        const { data: queuedJob } = await api.post<ResumeCompileJob>(
          `/api/resume/targets/${targetId}/compile`,
          { sections, selected_project_ids: selectedProjectIds },
        );
        if (!active) return;
        setCompileJob(queuedJob);

        const poll = async () => {
          try {
            const { data: job } = await api.get<ResumeCompileJob>(
              `/api/resume/jobs/${queuedJob.id}`,
            );
            if (!active) return;
            setCompileJob(job);
            if (job.status === "failed") {
              setCompileError(job.error || "Resume compilation failed.");
              return;
            }
            if (job.status !== "succeeded") {
              pollTimer = window.setTimeout(poll, 1000);
              return;
            }
            const { data: pdf } = await api.get<Blob>(
              `/api/resume/jobs/${job.id}/download/pdf`,
              { responseType: "blob" },
            );
            if (!active) return;
            previewObjectUrl = URL.createObjectURL(pdf);
            setPdfUrl(previewObjectUrl);
          } catch (requestError: unknown) {
            if (active) {
              setCompileError(
                getApiErrorMessage(requestError, "Could not load the PDF preview."),
              );
            }
          }
        };
        pollTimer = window.setTimeout(poll, 500);
      } catch (requestError: unknown) {
        if (active) {
          setCompileError(
            getApiErrorMessage(requestError, "Could not compile this resume."),
          );
        }
      }
    }, 400);

    return () => {
      active = false;
      window.clearTimeout(debounceTimer);
      if (pollTimer !== undefined) window.clearTimeout(pollTimer);
      if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
    };
  }, [loading, selection, sections, selectedProjectIds, targetId]);

  function toggleProject(projectId: string) {
    setSelectedProjectIds((current) =>
      current.includes(projectId)
        ? current.filter((id) => id !== projectId)
        : [...current, projectId],
    );
  }

  function handleDrop(event: DragEvent<HTMLLIElement>, targetProjectId: string) {
    event.preventDefault();
    if (!draggedProjectId || draggedProjectId === targetProjectId) return;
    const fromIndex = selectedProjectIds.indexOf(draggedProjectId);
    const toIndex = selectedProjectIds.indexOf(targetProjectId);
    if (fromIndex < 0 || toIndex < 0) return;
    setSelectedProjectIds((current) => reorder(current, fromIndex, toIndex));
    setDraggedProjectId(null);
  }

  function resetSelection() {
    setSelectedProjectIds(
      selection?.projects.slice(0, DEFAULT_PROJECT_LIMIT).map(({ item }) => item.id) ?? [],
    );
  }

  function toggleSection(section: keyof ResumeSections) {
    setSections((current) => ({ ...current, [section]: !current[section] }));
  }

  async function downloadArtifact(kind: "tex" | "pdf") {
    if (!compileJob || compileJob.status !== "succeeded") return;
    setCompileError("");
    try {
      const { data: file } = await api.get<Blob>(
        `/api/resume/jobs/${compileJob.id}/download/${kind}`,
        { responseType: "blob" },
      );
      const url = URL.createObjectURL(file);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `resume-${targetId}.${kind}`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (requestError: unknown) {
      setCompileError(
        getApiErrorMessage(requestError, `Could not download the ${kind.toUpperCase()} file.`),
      );
    }
  }

  async function openInOverleaf() {
    if (!compileJob || compileJob.status !== "succeeded") return;
    const windowName = `overleaf-resume-${Date.now()}`;
    const popup = window.open("about:blank", windowName);
    if (!popup) {
      setCompileError("Allow pop-ups to open this resume in Overleaf.");
      return;
    }
    setOpeningOverleaf(true);
    setCompileError("");
    try {
      const { data: snippet } = await api.get<{
        snip_uri: string;
        snip_name: string;
      }>(`/api/resume/jobs/${compileJob.id}/overleaf`);
      const form = document.createElement("form");
      form.method = "post";
      form.action = "https://www.overleaf.com/docs";
      form.target = windowName;
      for (const [name, value] of [
        ["snip_uri", snippet.snip_uri],
        ["snip_name", snippet.snip_name],
      ]) {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = name;
        input.value = value;
        form.appendChild(input);
      }
      document.body.appendChild(form);
      form.submit();
      form.remove();
    } catch (requestError: unknown) {
      popup.close();
      setCompileError(
        getApiErrorMessage(requestError, "Could not prepare the Overleaf import."),
      );
    } finally {
      setOpeningOverleaf(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar />
      <main className="mx-auto max-w-5xl space-y-6 px-4 py-8">
        <Link
          href={`/resume/targets/${targetId}`}
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-blue-600"
        >
          <ArrowLeft size={16} />
          Back to target
        </Link>

        {loading ? (
          <div role="status" className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
            Preparing your selection preview…
          </div>
        ) : error ? (
          <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
            {error}
          </div>
        ) : target && selection && afterCoverage ? (
          <>
            <header className="rounded-xl border border-slate-200 bg-white p-6">
              <p className="text-sm font-medium text-blue-600">Selection preview</p>
              <h1 className="mt-1 text-2xl font-bold text-slate-900">
                {target.role_title || "Resume selection"} · {target.company_name}
              </h1>
              <p className="mt-2 text-sm text-slate-600">
                Choose projects to include and drag selected projects to change their order.
                Scores update as you edit; this preview does not change your saved profile.
              </p>
            </header>

            <section className="grid gap-6 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
              <div className="space-y-5 rounded-xl border border-slate-200 bg-white p-6">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">Resume sections</h2>
                  <p className="mt-1 text-sm text-slate-500">
                    Changes compile automatically and update the PDF preview.
                  </p>
                </div>
                <fieldset className="space-y-3">
                  <legend className="sr-only">Sections included in the resume</legend>
                  {(
                    [
                      ["contact", "Contact information"],
                      ["education", "Education"],
                      ["projects", "Projects"],
                      ["skills", "Skills"],
                      ["certificates", "Certifications"],
                    ] as const
                  ).map(([section, label]) => (
                    <label key={section} className="flex items-center gap-3 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={sections[section]}
                        onChange={() => toggleSection(section)}
                        className="size-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                      />
                      {label}
                    </label>
                  ))}
                </fieldset>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void downloadArtifact("tex")}
                    disabled={compileJob?.status !== "succeeded"}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  >
                    <FileText size={16} /> Download .tex
                  </button>
                  <button
                    type="button"
                    onClick={() => void downloadArtifact("pdf")}
                    disabled={compileJob?.status !== "succeeded"}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  >
                    <Download size={16} /> Download .pdf
                  </button>
                  <button
                    type="button"
                    onClick={() => void openInOverleaf()}
                    disabled={compileJob?.status !== "succeeded" || openingOverleaf}
                    className="inline-flex items-center gap-2 rounded-lg bg-green-700 px-3 py-2 text-sm font-semibold text-white hover:bg-green-800 disabled:opacity-50"
                  >
                    <ExternalLink size={16} />
                    {openingOverleaf ? "Opening…" : "Open in Overleaf"}
                  </button>
                </div>
                <p className="text-xs text-slate-500">
                  Overleaf imports a copy of the TeX source. It does not connect or sync your account.
                </p>
                {compileJob && (
                  <p role="status" className="text-sm text-slate-600">
                    {compileJob.status === "queued" || compileJob.status === "running"
                      ? "Compiling resume…"
                      : compileJob.status === "succeeded"
                        ? "PDF preview is up to date."
                        : "Compilation failed."}
                  </p>
                )}
                {compileError && (
                  <p role="alert" className="text-sm text-red-700">{compileError}</p>
                )}
              </div>

              <section aria-label="Live PDF preview" className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                  <h2 className="font-semibold text-slate-900">Live PDF preview</h2>
                  {compileJob?.status === "succeeded" && (
                    <span className="text-xs text-green-700">Ready</span>
                  )}
                </div>
                {pdfUrl ? (
                  <iframe
                    title="Compiled resume PDF preview"
                    src={pdfUrl}
                    className="h-[760px] w-full bg-slate-100"
                  />
                ) : (
                  <div className="flex h-[360px] items-center justify-center p-8 text-center text-sm text-slate-500">
                    {compileError
                      ? "The PDF preview is unavailable."
                      : "Your PDF preview will appear when compilation finishes."}
                  </div>
                )}
              </section>
            </section>

            <section aria-labelledby="projects-heading" className="rounded-xl border border-slate-200 bg-white p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 id="projects-heading" className="text-lg font-semibold text-slate-900">
                    Project selection
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    {selectedProjects.length} selected · initial recommendation: top {DEFAULT_PROJECT_LIMIT}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={resetSelection}
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  <RotateCcw size={15} />
                  Reset selection
                </button>
              </div>
              <ul className="mt-4 space-y-3">
                {selection.projects.map(({ item, score, matched_keywords }) => {
                  const checked = selectedProjectIds.includes(item.id);
                  const order = selectedProjectIds.indexOf(item.id);
                  return (
                    <li
                      key={item.id}
                      onDragOver={(event) => event.preventDefault()}
                      onDrop={(event) => handleDrop(event, item.id)}
                      className={`rounded-lg border p-4 ${checked ? "border-blue-200 bg-blue-50/50" : "border-slate-200"}`}
                    >
                      <div className="flex items-start gap-3">
                        {checked && (
                          <span
                            draggable
                            onDragStart={() => setDraggedProjectId(item.id)}
                            onDragEnd={() => setDraggedProjectId(null)}
                            aria-label={`Drag to reorder ${item.title}`}
                            className="mt-1 cursor-grab touch-none text-slate-400 active:cursor-grabbing"
                            title="Drag to reorder"
                          >
                            <GripVertical size={18} />
                          </span>
                        )}
                        <input
                          id={`project-${item.id}`}
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleProject(item.id)}
                          className="mt-1 size-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        />
                        <label htmlFor={`project-${item.id}`} className="min-w-0 flex-1 cursor-pointer">
                          <span className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-slate-900">{item.title}</span>
                            {checked && (
                              <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                                Selected #{order + 1}
                              </span>
                            )}
                          </span>
                          {item.tech_stack.length > 0 && (
                            <span className="mt-1 block text-sm text-slate-600">
                              {item.tech_stack.join(" · ")}
                            </span>
                          )}
                          {item.bullets.length > 0 && (
                            <span className="mt-2 block text-sm text-slate-600">
                              {item.bullets.join(" · ")}
                            </span>
                          )}
                          <span className="mt-2 block text-xs text-slate-500">
                            Match {Math.round(score * 100)}%
                            {matched_keywords.length > 0 &&
                              ` · Keywords: ${matched_keywords.join(", ")}`}
                          </span>
                        </label>
                      </div>
                    </li>
                  );
                })}
                {selection.projects.length === 0 && (
                  <li className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
                    No projects are available in this resume profile.
                  </li>
                )}
              </ul>
            </section>

            <section aria-labelledby="ats-heading" className="rounded-xl border border-slate-200 bg-white p-6">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h2 id="ats-heading" className="text-lg font-semibold text-slate-900">ATS keyword coverage</h2>
                  <p className="mt-1 text-sm text-slate-500">
                    Required JD keywords carry twice the weight of preferred keywords.
                  </p>
                </div>
                <div className="flex gap-3">
                  <CoverageScore label="Before" score={selection.keyword_coverage.before.score} />
                  <CoverageScore label="After" score={afterCoverage.score} emphasized />
                </div>
              </div>
              <div className="mt-5 grid gap-6 md:grid-cols-2">
                <div className="space-y-4">
                  <h3 className="font-semibold text-slate-800">Before · full profile</h3>
                  <KeywordList title="Matched" keywords={selection.keyword_coverage.before.matched_keywords} positive />
                  <KeywordList title="Missing" keywords={selection.keyword_coverage.before.missing_keywords} />
                </div>
                <div className="space-y-4 border-t border-slate-100 pt-5 md:border-l md:border-t-0 md:pl-6 md:pt-0">
                  <h3 className="font-semibold text-slate-800">After · preview selection</h3>
                  <KeywordList title="Matched" keywords={afterCoverage.matched_keywords} positive />
                  <KeywordList title="Missing" keywords={afterCoverage.missing_keywords} />
                </div>
              </div>
            </section>
          </>
        ) : null}
      </main>
    </div>
  );
}

function CoverageScore({
  label,
  score,
  emphasized = false,
}: {
  label: string;
  score: number;
  emphasized?: boolean;
}) {
  return (
    <div className={`rounded-xl px-4 py-3 text-center ${emphasized ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-800"}`}>
      <p className={`text-xs font-medium ${emphasized ? "text-blue-100" : "text-slate-500"}`}>{label}</p>
      <p className="mt-0.5 text-2xl font-bold">{Math.round(score * 100)}%</p>
    </div>
  );
}

function KeywordList({
  title,
  keywords,
  positive = false,
}: {
  title: string;
  keywords: string[];
  positive?: boolean;
}) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
      {keywords.length ? (
        <ul className="mt-2 flex flex-wrap gap-2">
          {keywords.map((keyword) => (
            <li
              key={keyword}
              className={`rounded-full px-2.5 py-1 text-xs font-medium ${positive ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-800"}`}
            >
              {keyword}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-slate-500">None</p>
      )}
    </div>
  );
}
