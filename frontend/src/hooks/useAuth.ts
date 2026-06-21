"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { saveTokens, clearTokens } from "@/lib/auth";
import { User } from "@/lib/types";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setLoading(false);
      return;
    }
    api.get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => {
        clearTokens();
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const r = await api.post("/auth/login", { email, password });
    saveTokens(r.data.access_token, r.data.refresh_token);
    const me = await api.get("/auth/me");
    setUser(me.data);
    router.push("/dashboard");
  }

  async function register(full_name: string, email: string, password: string, whatsapp_number?: string) {
    const r = await api.post("/auth/register", { full_name, email, password, whatsapp_number });
    saveTokens(r.data.access_token, r.data.refresh_token);
    const me = await api.get("/auth/me");
    setUser(me.data);
    router.push("/dashboard");
  }

  async function logout() {
    const refresh_token = localStorage.getItem("refresh_token");
    if (refresh_token) {
      try { await api.post("/auth/logout", { refresh_token }); } catch {}
    }
    clearTokens();
    setUser(null);
    router.push("/login");
  }

  return { user, loading, login, register, logout };
}
