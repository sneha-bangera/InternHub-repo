"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { FileText, Search } from "lucide-react";
import Navbar from "@/components/Navbar";
import { api, getApiErrorMessage } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import { Listing, ListingPage } from "@/lib/types";

type InputMode = "paste" | "listing";

export default function NewTargetPage() {
  const router = useRouter();
  const [mode, setMode] = useState<InputMode>("paste");
  const [jdText, setJdText] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [listingId, setListingId] = useState("");
  const [listings, setListings] = useState<Listing[]>([]);
  const [listingSearch, setListingSearch] = useState("");
  const [loadingListings, setLoadingListings] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    async function loadListings() {
      setLoadingListings(true);
      setError("");
      try {
        const firstPage = await api.get<ListingPage>("/listings", {
          params: { page: 1, page_size: 100 },
        });
        const remainingPages = await Promise.all(
          Array.from({ length: Math.max(0, firstPage.data.pages - 1) }, (_, index) =>
            api.get<ListingPage>("/listings", {
              params: { page: index + 2, page_size: 100 },
            }),
          ),
        );
        setListings([
          ...firstPage.data.items,
          ...remainingPages.flatMap(({ data }) => data.items),
        ]);
      } catch (requestError: unknown) {
        setError(getApiErrorMessage(requestError, "Could not load internship listings."));
      } finally {
        setLoadingListings(false);
      }
    }
    void loadListings();
  }, [router]);

  const filteredListings = useMemo(() => {
    const query = listingSearch.trim().toLowerCase();
    if (!query) return listings;
    return listings.filter((listing) =>
      `${listing.title} ${listing.company} ${listing.source_platform}`.toLowerCase().includes(query),
    );
  }, [listings, listingSearch]);

  async function createTarget(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    const payload = mode === "paste"
      ? {
          jd_text: jdText.trim(),
          company_name: companyName.trim(),
          ...(roleTitle.trim() ? { role_title: roleTitle.trim() } : {}),
        }
      : { listing_id: listingId };

    try {
      const response = await api.post<{ id: string }>("/api/resume/jd/parse", payload);
      router.push(`/resume/targets/${response.data.id}`);
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, "Could not parse this job description. Please try again."));
    } finally {
      setSubmitting(false);
    }
  }

  const selectedListing = listings.find((listing) => listing.id === listingId);

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar />
      <main className="mx-auto max-w-3xl px-4 py-8">
        <header className="mb-6">
          <div className="flex items-center gap-2 text-blue-500">
            <FileText size={20} />
            <span className="text-sm font-semibold uppercase tracking-wide">Resume tools</span>
          </div>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">New Target</h1>
          <p className="mt-1 text-sm text-slate-500">
            Add a job description to extract the role requirements for a tailored resume.
          </p>
        </header>

        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <div className="mb-6 grid grid-cols-2 gap-2 rounded-lg bg-slate-100 p-1">
            <button
              type="button"
              onClick={() => { setMode("paste"); setError(""); }}
              className={`rounded-md px-3 py-2 text-sm font-medium ${mode === "paste" ? "bg-white text-blue-600 shadow-sm" : "text-slate-600 hover:text-slate-900"}`}
            >
              Paste a job description
            </button>
            <button
              type="button"
              onClick={() => { setMode("listing"); setError(""); }}
              className={`rounded-md px-3 py-2 text-sm font-medium ${mode === "listing" ? "bg-white text-blue-600 shadow-sm" : "text-slate-600 hover:text-slate-900"}`}
            >
              Choose an InternHub listing
            </button>
          </div>

          <form onSubmit={createTarget} className="space-y-4">
            {mode === "paste" ? (
              <>
                <label className="block space-y-1.5 text-sm font-medium text-slate-700">
                  <span>Company name</span>
                  <input
                    required
                    maxLength={255}
                    value={companyName}
                    onChange={(event) => setCompanyName(event.target.value)}
                    placeholder="e.g. Acme"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 font-normal focus:outline-none focus:ring-2 focus:ring-blue-300"
                  />
                </label>
                <label className="block space-y-1.5 text-sm font-medium text-slate-700">
                  <span>Role title <span className="font-normal text-slate-400">(optional)</span></span>
                  <input
                    maxLength={255}
                    value={roleTitle}
                    onChange={(event) => setRoleTitle(event.target.value)}
                    placeholder="e.g. Software Engineering Intern"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 font-normal focus:outline-none focus:ring-2 focus:ring-blue-300"
                  />
                </label>
                <label className="block space-y-1.5 text-sm font-medium text-slate-700">
                  <span>Job description</span>
                  <textarea
                    required
                    minLength={20}
                    rows={11}
                    value={jdText}
                    onChange={(event) => setJdText(event.target.value)}
                    placeholder="Paste the complete job description here…"
                    className="w-full resize-y rounded-lg border border-slate-300 px-3 py-2 font-normal focus:outline-none focus:ring-2 focus:ring-blue-300"
                  />
                  <span className="block text-right text-xs font-normal text-slate-400">
                    {jdText.length} characters
                  </span>
                </label>
              </>
            ) : (
              <>
                <label className="block space-y-1.5 text-sm font-medium text-slate-700">
                  <span>Find a listing</span>
                  <div className="relative">
                    <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                      value={listingSearch}
                      onChange={(event) => setListingSearch(event.target.value)}
                      placeholder="Search title, company, or source…"
                      className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 font-normal focus:outline-none focus:ring-2 focus:ring-blue-300"
                    />
                  </div>
                </label>
                <label className="block space-y-1.5 text-sm font-medium text-slate-700">
                  <span>InternHub listing</span>
                  <select
                    required
                    value={listingId}
                    onChange={(event) => setListingId(event.target.value)}
                    disabled={loadingListings}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:opacity-60"
                  >
                    <option value="">{loadingListings ? "Loading listings…" : "Select a listing"}</option>
                    {filteredListings.map((listing) => (
                      <option key={listing.id} value={listing.id}>
                        {listing.title} · {listing.company} ({listing.source_platform})
                      </option>
                    ))}
                  </select>
                  {!loadingListings && filteredListings.length === 0 && (
                    <span className="block text-xs font-normal text-slate-500">No listings match that search.</span>
                  )}
                </label>
                {selectedListing && (
                  <div className="rounded-lg border border-slate-100 bg-slate-50 p-4 text-sm">
                    <p className="font-semibold text-slate-800">{selectedListing.title}</p>
                    <p className="mt-1 text-slate-500">{selectedListing.company} · {selectedListing.source_platform}</p>
                    {selectedListing.description && (
                      <p className="mt-3 line-clamp-5 whitespace-pre-line text-xs text-slate-600">
                        {selectedListing.description}
                      </p>
                    )}
                  </div>
                )}
              </>
            )}

            {error && (
              <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}
            <button
              type="submit"
              disabled={submitting || (mode === "listing" && (loadingListings || !listingId))}
              className="w-full rounded-lg bg-blue-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
            >
              {submitting ? "Parsing job description…" : "Parse job description"}
            </button>
            {submitting && (
              <p role="status" className="text-sm text-slate-500">
                Extracting role details, skills, and keywords. This may take a few seconds.
              </p>
            )}
          </form>
        </section>
      </main>
    </div>
  );
}
