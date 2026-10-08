"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Award, FileUser, FolderGit2, GraduationCap, Pencil, Plus, Trash2, Wrench, X } from "lucide-react";
import Navbar from "@/components/Navbar";
import { api, getApiErrorMessage, isApiNotFound } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import { ResumeProfile } from "@/lib/types";

type SectionKey = "education" | "projects" | "skills" | "certificates";
type FormValue = string | string[] | null;
type ResumeRecord = { id: string; profile_id: string; [key: string]: FormValue };

interface SectionField {
  key: string;
  label: string;
  type?: "text" | "date" | "list" | "textarea" | "url";
  required?: boolean;
  placeholder?: string;
}

interface SectionConfig {
  key: SectionKey;
  title: string;
  path: string;
  empty: string;
  icon: typeof GraduationCap;
  fields: SectionField[];
}

const SECTIONS: SectionConfig[] = [
  {
    key: "education",
    title: "Education",
    path: "education",
    empty: "Add schools, degrees, and dates.",
    icon: GraduationCap,
    fields: [
      { key: "institution", label: "Institution", required: true },
      { key: "degree", label: "Degree" },
      { key: "field_of_study", label: "Field of study" },
      { key: "start_date", label: "Start date", type: "date" },
      { key: "end_date", label: "End date", type: "date" },
    ],
  },
  {
    key: "projects",
    title: "Projects",
    path: "projects",
    empty: "Showcase projects and the work you did.",
    icon: FolderGit2,
    fields: [
      { key: "title", label: "Project title", required: true },
      { key: "tech_stack", label: "Tech stack", type: "list", placeholder: "One per line" },
      { key: "bullets", label: "Highlights", type: "list", placeholder: "One achievement per line" },
      { key: "start_date", label: "Start date", type: "date" },
      { key: "end_date", label: "End date", type: "date" },
      { key: "url", label: "Project URL", type: "url" },
    ],
  },
  {
    key: "skills",
    title: "Skills",
    path: "skills",
    empty: "Add skills and group them by category.",
    icon: Wrench,
    fields: [
      { key: "name", label: "Skill", required: true },
      { key: "category", label: "Category" },
      { key: "proficiency", label: "Proficiency", placeholder: "e.g. Intermediate" },
    ],
  },
  {
    key: "certificates",
    title: "Certificates",
    path: "certificates",
    empty: "Add certifications and credentials.",
    icon: Award,
    fields: [
      { key: "name", label: "Certificate", required: true },
      { key: "issuer", label: "Issuer" },
      { key: "date", label: "Date", type: "date" },
      { key: "url", label: "Credential URL", type: "url" },
    ],
  },
];

const emptySections: Record<SectionKey, ResumeRecord[]> = {
  education: [],
  projects: [],
  skills: [],
  certificates: [],
};

function recordText(value: FormValue | undefined): string {
  if (Array.isArray(value)) return value.join("\n");
  return value ?? "";
}

function displayValue(value: FormValue | undefined): string {
  if (Array.isArray(value)) return value.join(", ");
  return value || "";
}

export default function ResumeProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<ResumeProfile | null>(null);
  const [profileDraft, setProfileDraft] = useState({
    name: "", email: "", phone: "", links: "",
  });
  const [sections, setSections] = useState(emptySections);
  const [activeSection, setActiveSection] = useState<SectionKey | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingItem, setSavingItem] = useState(false);
  const [error, setError] = useState("");

  const loadSections = useCallback(async () => {
    const entries = await Promise.all(
      SECTIONS.map(async (section) => {
        const response = await api.get<ResumeRecord[]>(
          `/api/resume/profile/${section.path}`,
        );
        return [section.key, response.data] as const;
      }),
    );
    setSections(Object.fromEntries(entries) as Record<SectionKey, ResumeRecord[]>);
  }, []);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    api.get<ResumeProfile>("/api/resume/profile")
      .then(async ({ data }) => {
        setProfile(data);
        setProfileDraft({
          name: data.name,
          email: data.email ?? "",
          phone: data.phone ?? "",
          links: data.links.join("\n"),
        });
        await loadSections();
      })
      .catch((requestError: unknown) => {
        if (!isApiNotFound(requestError)) {
          setError(getApiErrorMessage(requestError, "Could not load your resume profile."));
        }
      })
      .finally(() => setLoading(false));
  }, [loadSections, router]);

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    setSavingProfile(true);
    setError("");
    const payload = {
      name: profileDraft.name.trim(),
      email: profileDraft.email.trim() || null,
      phone: profileDraft.phone.trim() || null,
      links: profileDraft.links.split("\n").map((link) => link.trim()).filter(Boolean),
    };
    try {
      const response = profile
        ? await api.patch<ResumeProfile>("/api/resume/profile", payload)
        : await api.post<ResumeProfile>("/api/resume/profile", payload);
      setProfile(response.data);
      await loadSections();
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, "Could not save your resume profile."));
    } finally {
      setSavingProfile(false);
    }
  }

  function openForm(section: SectionConfig, item?: ResumeRecord) {
    setActiveSection(section.key);
    setEditingId(item?.id ?? null);
    setDraft(Object.fromEntries(
      section.fields.map((field) => [field.key, recordText(item?.[field.key])]),
    ));
    setError("");
  }

  function closeForm() {
    setActiveSection(null);
    setEditingId(null);
    setDraft({});
  }

  async function saveItem(event: FormEvent) {
    event.preventDefault();
    if (!activeSection) return;
    const section = SECTIONS.find(({ key }) => key === activeSection);
    if (!section) return;

    const payload: Record<string, FormValue> = {};
    for (const field of section.fields) {
      const value = draft[field.key]?.trim() ?? "";
      if (field.type === "list") {
        payload[field.key] = value.split("\n").map((line) => line.trim()).filter(Boolean);
      } else {
        payload[field.key] = value || (field.required ? "" : null);
      }
    }

    setSavingItem(true);
    setError("");
    try {
      const endpoint = `/api/resume/profile/${section.path}`;
      const response = editingId
        ? await api.patch<ResumeRecord>(`${endpoint}/${editingId}`, payload)
        : await api.post<ResumeRecord>(endpoint, payload);
      setSections((current) => ({
        ...current,
        [section.key]: editingId
          ? current[section.key].map((item) => item.id === editingId ? response.data : item)
          : [...current[section.key], response.data],
      }));
      closeForm();
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, "Could not save this item."));
    } finally {
      setSavingItem(false);
    }
  }

  async function deleteItem(section: SectionConfig, id: string) {
    if (!window.confirm(`Delete this ${section.title.toLowerCase()} item?`)) return;
    setError("");
    try {
      await api.delete(`/api/resume/profile/${section.path}/${id}`);
      setSections((current) => ({
        ...current,
        [section.key]: current[section.key].filter((item) => item.id !== id),
      }));
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, "Could not delete this item."));
    }
  }

  const profileFields: [keyof typeof profileDraft, string, "text" | "email" | "tel" | "textarea"][] = [
    ["name", "Name", "text"],
    ["email", "Email", "email"],
    ["phone", "Phone", "tel"],
    ["links", "Links (one URL per line)", "textarea"],
  ];

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar />
      <main className="mx-auto max-w-4xl space-y-6 px-4 py-8">
        <header>
          <div className="flex items-center gap-2 text-blue-500">
            <FileUser size={20} />
            <span className="text-sm font-semibold uppercase tracking-wide">Resume tools</span>
          </div>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">Resume Profile</h1>
          <p className="mt-1 text-sm text-slate-500">
            Keep your experience and skills in one place to tailor your resume for each role.
          </p>
        </header>

        {error && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {loading ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
            Loading your resume profile…
          </div>
        ) : (
          <>
            <section className="rounded-xl border border-slate-200 bg-white p-6">
              <h2 className="mb-4 text-lg font-semibold text-slate-900">Contact details</h2>
              <form onSubmit={saveProfile} className="grid gap-4 sm:grid-cols-2">
                {profileFields.map(([key, label, type]) => (
                  <label key={key} className={`space-y-1.5 text-sm font-medium text-slate-700 ${type === "textarea" ? "sm:col-span-2" : ""}`}>
                    <span>{label}</span>
                    {type === "textarea" ? (
                      <textarea
                        rows={3}
                        value={profileDraft[key]}
                        onChange={(event) => setProfileDraft({ ...profileDraft, [key]: event.target.value })}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 font-normal focus:outline-none focus:ring-2 focus:ring-blue-300"
                        placeholder="https://portfolio.example"
                      />
                    ) : (
                      <input
                        type={type}
                        required={key === "name"}
                        value={profileDraft[key]}
                        onChange={(event) => setProfileDraft({ ...profileDraft, [key]: event.target.value })}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 font-normal focus:outline-none focus:ring-2 focus:ring-blue-300"
                      />
                    )}
                  </label>
                ))}
                <div className="sm:col-span-2">
                  <button
                    type="submit"
                    disabled={savingProfile}
                    className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-600 disabled:opacity-50"
                  >
                    {savingProfile ? "Saving…" : profile ? "Save contact details" : "Create resume profile"}
                  </button>
                </div>
              </form>
              {!profile && (
                <p className="mt-3 text-xs text-slate-500">
                  Create your profile before adding education, projects, skills, or certificates.
                </p>
              )}
            </section>

            {SECTIONS.map((section) => {
              const Icon = section.icon;
              const isOpen = activeSection === section.key;
              return (
                <section key={section.key} className="rounded-xl border border-slate-200 bg-white p-6">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900">
                      <Icon size={19} className="text-blue-500" />
                      {section.title}
                      <span className="text-sm font-normal text-slate-400">
                        ({sections[section.key].length})
                      </span>
                    </h2>
                    <button
                      type="button"
                      disabled={!profile}
                      onClick={() => isOpen && !editingId ? closeForm() : openForm(section)}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                    >
                      {isOpen && !editingId ? <X size={15} /> : <Plus size={15} />}
                      {isOpen && !editingId ? "Cancel" : "Add"}
                    </button>
                  </div>

                  {isOpen && (
                    <form onSubmit={saveItem} className="mb-5 rounded-lg bg-slate-50 p-4">
                      <div className="grid gap-3 sm:grid-cols-2">
                        {section.fields.map((field) => (
                          <label key={field.key} className={`space-y-1 text-sm font-medium text-slate-700 ${field.type === "list" ? "sm:col-span-2" : ""}`}>
                            <span>{field.label}</span>
                            {field.type === "list" || field.type === "textarea" ? (
                              <textarea
                                rows={field.type === "list" ? 3 : 2}
                                required={field.required}
                                value={draft[field.key] ?? ""}
                                onChange={(event) => setDraft({ ...draft, [field.key]: event.target.value })}
                                placeholder={field.placeholder}
                                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal focus:outline-none focus:ring-2 focus:ring-blue-300"
                              />
                            ) : (
                              <input
                                type={field.type ?? "text"}
                                required={field.required}
                                value={draft[field.key] ?? ""}
                                onChange={(event) => setDraft({ ...draft, [field.key]: event.target.value })}
                                placeholder={field.placeholder}
                                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal focus:outline-none focus:ring-2 focus:ring-blue-300"
                              />
                            )}
                          </label>
                        ))}
                      </div>
                      <div className="mt-4 flex gap-2">
                        <button
                          type="submit"
                          disabled={savingItem}
                          className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:opacity-50"
                        >
                          {savingItem ? "Saving…" : editingId ? "Save changes" : `Add ${section.title.toLowerCase()}`}
                        </button>
                        <button type="button" onClick={closeForm} className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-white">
                          Cancel
                        </button>
                      </div>
                    </form>
                  )}

                  {sections[section.key].length === 0 ? (
                    <p className="text-sm text-slate-400">{section.empty}</p>
                  ) : (
                    <div className="divide-y divide-slate-100">
                      {sections[section.key].map((item) => (
                        <article key={item.id} className="flex items-start gap-3 py-4 first:pt-0 last:pb-0">
                          <div className="min-w-0 flex-1">
                            {section.fields.map((field) => {
                              const text = displayValue(item[field.key]);
                              if (!text) return null;
                              return (
                                <p key={field.key} className={field.required ? "font-medium text-slate-800" : "mt-1 text-sm text-slate-500"}>
                                  {field.type === "date" ? new Date(`${text}T00:00:00`).toLocaleDateString() : text}
                                </p>
                              );
                            })}
                          </div>
                          <div className="flex shrink-0 gap-1">
                            <button
                              type="button"
                              aria-label={`Edit ${section.title.toLowerCase()} item`}
                              onClick={() => openForm(section, item)}
                              className="rounded-md p-2 text-slate-400 hover:bg-slate-100 hover:text-blue-600"
                            >
                              <Pencil size={16} />
                            </button>
                            <button
                              type="button"
                              aria-label={`Delete ${section.title.toLowerCase()} item`}
                              onClick={() => deleteItem(section, item.id)}
                              className="rounded-md p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </section>
              );
            })}
          </>
        )}
      </main>
    </div>
  );
}
