// Typed fetch client για το ProspectMatch API.
//
// Base URL: VITE_API_BASE (build-time) ή localhost:8000 default.
// Στο packaged Electron, ο backend τρέχει στο 127.0.0.1:8000 (ίδιο default).

import type {
  StatsMetaResponse,
  ArchetypesResponse,
  SimilarRequest,
  SimilarResponse,
  ClassifyResponse,
} from "./types";

const BASE =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    // Network-level: backend down / CORS / DNS
    throw new ApiError(0, `Δεν βρέθηκε ο server (${BASE}). Τρέχει ο backend;`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  base: BASE,

  health: () => request<{ status: string; players: number; rows: number }>("/health"),

  statsMeta: () => request<StatsMetaResponse>("/stats"),

  archetypes: () => request<ArchetypesResponse>("/archetypes"),

  similar: (body: SimilarRequest) =>
    request<SimilarResponse>("/similar", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  classify: (player_name: string, season?: string) =>
    request<ClassifyResponse>("/classify", {
      method: "POST",
      body: JSON.stringify({ player_name, season }),
    }),

  players: (q: string) =>
    request<{ players: string[] }>(`/players?q=${encodeURIComponent(q)}`),
};

export { ApiError };
