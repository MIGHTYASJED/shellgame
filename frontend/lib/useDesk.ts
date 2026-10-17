"use client";
import { useEffect, useState } from "react";

const KEY = "shellgame.desk";
export function useDesk(): [string, (d: string) => void] {
  const [desk, setDesk] = useState("default");
  useEffect(() => {
    try {
      const u = new URLSearchParams(window.location.search).get("tenant");
      const s = u || localStorage.getItem(KEY);
      if (s) setDesk(s);
    } catch {}
  }, []);
  const set = (d: string) => {
    const clean = d.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "") || "default";
    setDesk(clean);
    try { localStorage.setItem(KEY, clean); } catch {}
  };
  return [desk, set];
}
