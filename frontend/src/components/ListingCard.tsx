"use client";
import { Listing } from "@/lib/types";
import { api } from "@/lib/api";
import { useState } from "react";

const PLATFORM_COLORS: Record<string, string> = {
  internshala: "bg-green-100 text-green-700",
  linkedin: "bg-blue-100 text-blue-700",
  wellfound: "bg-orange-100 text-orange-700",
};

const STATUS_COLORS = {
  saved: "bg-slate-100 text-slate-600",
  applied: "bg-blue-100 text-blue-600",
  rejected: "bg-red-100 text-red-600",
  accepted: "bg-green-100 text-green-600",
};

function daysLeft(deadline: string | null) {
  if (!deadline) return null;
  const diff = Math.ceil((new Date(deadline).getTime() - Date.now()) / 86400000);
  return diff;
}

export default function ListingCard({ listing }: { listing: Listing }) {
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const days = daysLeft(listing.deadline);

  async function saveInternship() {
    setSaving(true);
    try {
      await api.post("/applications", { listing_id: listing.id, status: "saved" });
      setSaved(true);
    } catch (e: any) {
      // 409 / already saved
      setSaved(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 hover:shadow-md transition-shadow flex flex-col gap-3">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-slate-900 text-base leading-tight truncate">{listing.title}</h3>
          <p className="text-slate-500 text-sm mt-0.5">{listing.company}</p>
        </div>
        <span className={`shrink-0 text-xs font-medium px-2 py-1 rounded-full capitalize ${PLATFORM_COLORS[listing.source_platform] ?? "bg-slate-100 text-slate-600"}`}>
          {listing.source_platform}
        </span>
      </div>

      {/* Meta row */}
      <div className="flex flex-wrap gap-2 text-xs text-slate-500">
        {listing.location && <span>📍 {listing.location}</span>}
        {listing.stipend && <span>💰 {listing.stipend}</span>}
        {listing.duration && <span>⏱ {listing.duration}</span>}
      </div>

      {/* Skills */}
      {listing.skills_required && (
        <div className="flex flex-wrap gap-1.5">
          {listing.skills_required.split(",").slice(0, 5).map((s) => (
            <span key={s} className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">
              {s.trim()}
            </span>
          ))}
        </div>
      )}

      {/* Match score bar */}
      {listing.match_score !== undefined && listing.match_score !== null && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-slate-500">Match score</span>
            <span className={`font-medium ${listing.match_score >= 0.7 ? "text-green-600" : listing.match_score >= 0.4 ? "text-yellow-600" : "text-slate-500"}`}>
              {Math.round(listing.match_score * 100)}%
            </span>
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${listing.match_score >= 0.7 ? "bg-green-500" : listing.match_score >= 0.4 ? "bg-yellow-500" : "bg-slate-300"}`}
              style={{ width: `${listing.match_score * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-1 border-t border-slate-100 mt-auto">
        {days !== null ? (
          <span className={`text-xs font-medium ${days <= 3 ? "text-red-600" : days <= 7 ? "text-orange-500" : "text-slate-400"}`}>
            {days <= 0 ? "Deadline passed" : `${days}d left`}
          </span>
        ) : <span />}
        <div className="flex gap-2">
          <button
            onClick={saveInternship} disabled={saving || saved}
            className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50 transition-colors"
          >
            {saved ? "✓ Saved" : saving ? "…" : "Save"}
          </button>
          <a
            href={listing.apply_url} target="_blank" rel="noopener noreferrer"
            className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors font-medium"
          >
            Apply →
          </a>
        </div>
      </div>
    </div>
  );
}
