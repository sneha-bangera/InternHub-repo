"use client";

import { DragEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, GripVertical, RotateCcw } from "lucide-react";
import Navbar from "@/components/Navbar";
import { api, getApiErrorMessage } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import {
  JobTarget,
  KeywordCoverage,
  ResumeProject,
  ResumeSelection,
} from "@/lib/types";

const DEFAULT_PROJECT_LIMIT = 4;
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
