"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import { ListingPage } from "@/lib/types";
import Navbar from "@/components/Navbar";
import ListingCard from "@/components/ListingCard";

const PLATFORMS = ["all", "internshala", "linkedin", "wellfound"];

export default function DashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<ListingPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [platform, setPlatform] = useState("all");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [useRanked, setUseRanked] = useState(true);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace("/login"); return; }
  }, [router]);

  const fetchListings = useCallback(async () => {
    setLoading(true);
    try {
      const endpoint = useRanked ? "/listings/ranked" : "/listings";
      const params: Record<string, any> = { page, page_size: 12 };
      if (platform !== "all") params.platform = platform;
      if (search) params.search = search;
      const r = await api.get(endpoint, { params });
      setData(r.data);
    } catch {
      router.replace("/login");
    } finally {
      setLoading(false);
    }
  }, [page, platform, search, useRanked, router]);

  useEffect(() => { fetchListings(); }, [fetchListings]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  }

  function handlePlatform(p: string) {
    setPlatform(p);
    setPage(1);
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 py-8">

        {/* Header */}
        <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Internship Listings</h2>
            <p className="text-slate-500 text-sm mt-1">
              {data ? `${data.total} internships found` : "Loading…"}
              {useRanked && data && data.total > 0 && (
                <span className="ml-2 text-blue-500">· ranked by skill match</span>
              )}
            </p>
          </div>
          {/* Ranked toggle */}
          <button
            onClick={() => { setUseRanked((r) => !r); setPage(1); }}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
              useRanked
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-white text-slate-600 border-slate-300 hover:bg-slate-50"
            }`}
          >
            <span>{useRanked ? "✨" : "☰"}</span>
            {useRanked ? "Ranked by Skills" : "Default Order"}
          </button>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <form onSubmit={handleSearch} className="flex gap-2 flex-1">
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search by title or company…"
              className="flex-1 px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button type="submit"
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors">
              Search
            </button>
            {search && (
              <button type="button"
                onClick={() => { setSearch(""); setSearchInput(""); setPage(1); }}
                className="px-3 py-2 text-sm text-slate-500 border border-slate-300 rounded-lg hover:bg-slate-50">
                Clear
              </button>
            )}
          </form>
          <div className="flex gap-1.5">
            {PLATFORMS.map((p) => (
              <button key={p} onClick={() => handlePlatform(p)}
                className={`px-3 py-2 text-xs font-medium rounded-lg capitalize transition-colors ${
                  platform === p
                    ? "bg-blue-600 text-white"
                    : "bg-white border border-slate-300 text-slate-600 hover:bg-slate-50"
                }`}>
                {p}
              </button>
            ))}
          </div>
        </div>

        {/* No skills notice */}
        {useRanked && data && data.items.length > 0 && data.items[0].match_score === 0 && (
          <div className="mb-4 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
            💡 Add skills to your{" "}
            <a href="/profile" className="underline font-medium">profile</a>{" "}
            to get personalised match scores.
          </div>
        )}

        {/* Grid */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-52 bg-white border border-slate-200 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : data && data.items.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.items.map((l) => <ListingCard key={l.id} listing={l} />)}
          </div>
        ) : (
          <div className="text-center py-20 text-slate-400">
            <p className="text-4xl mb-3">🔍</p>
            <p className="font-medium">No listings found</p>
            <p className="text-sm mt-1">Try changing the filters or run the scrapers</p>
          </div>
        )}

        {/* Pagination */}
        {data && data.pages > 1 && (
          <div className="flex justify-center items-center gap-3 mt-8">
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
              className="px-4 py-2 text-sm border border-slate-300 rounded-lg disabled:opacity-40 hover:bg-slate-50">
              ← Previous
            </button>
            <span className="text-sm text-slate-500">Page {data.page} of {data.pages}</span>
            <button onClick={() => setPage((p) => Math.min(data.pages, p + 1))} disabled={page === data.pages}
              className="px-4 py-2 text-sm border border-slate-300 rounded-lg disabled:opacity-40 hover:bg-slate-50">
              Next →
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
