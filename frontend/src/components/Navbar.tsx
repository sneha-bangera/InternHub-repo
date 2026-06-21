"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, ClipboardList, User, LogOut, Target } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

export default function Navbar() {
  const { user, logout } = useAuth();
  const path = usePathname();

  const linkClass = (href: string) =>
    `flex items-center gap-1.5 text-sm font-medium transition-colors ${
      path === href ? "text-blue-600" : "text-slate-600 hover:text-blue-600"
    }`;

  return (
    <nav className="border-b border-slate-200 bg-white sticky top-0 z-10">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link href="/dashboard" className="flex items-center gap-2 text-xl font-bold text-blue-600">
          <Target size={22} />
          InternHub
        </Link>
        <div className="flex items-center gap-6">
          <Link href="/dashboard" className={linkClass("/dashboard")}>
            <LayoutDashboard size={16} />
            Dashboard
          </Link>
          <Link href="/tracker" className={linkClass("/tracker")}>
            <ClipboardList size={16} />
            Tracker
          </Link>
          <Link href="/profile" className={linkClass("/profile")}>
            <User size={16} />
            Profile
          </Link>
          <div className="flex items-center gap-3 pl-4 border-l border-slate-200">
            <span className="text-sm text-slate-500 hidden sm:block">{user?.full_name}</span>
            <button
              onClick={logout}
              className="flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-red-600 transition-colors"
            >
              <LogOut size={16} />
              Logout
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}