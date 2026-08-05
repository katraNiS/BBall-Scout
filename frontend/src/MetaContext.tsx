// Context για τα /stats metadata (feature ranges/labels + traits).
//
// Γιατί context και όχι fetch ανά screen: χωρίς αυτό, κάθε screen που χρειάζεται
// τα stats metadata (Search τώρα, Prospects/ProspectForm αργότερα για prefill) θα
// έκανε δικό του fetch στο mount — άρα re-fetch κάθε φορά που ο χρήστης πλοηγείται
// μακριά και πίσω. Το provider φορτώνει μία φορά, στο mount του App shell.

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "./api";
import type { StatMeta } from "./types";

interface MetaContextValue {
  stats: StatMeta[];
  traits: string[];
  traitLabels: Record<string, string>;
  loading: boolean;
  error: string | null;
  backendOk: boolean | null;
}

const MetaContext = createContext<MetaContextValue | null>(null);

export function MetaProvider({ children }: { children: ReactNode }) {
  const [stats, setStats] = useState<StatMeta[]>([]);
  const [traits, setTraits] = useState<string[]>([]);
  const [traitLabels, setTraitLabels] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const meta = await api.statsMeta();
        setStats(meta.stats);
        setTraits(meta.traits);
        setTraitLabels(meta.trait_labels);
        setBackendOk(true);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
        setBackendOk(false);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <MetaContext.Provider value={{ stats, traits, traitLabels, loading, error, backendOk }}>
      {children}
    </MetaContext.Provider>
  );
}

export function useMeta(): MetaContextValue {
  const ctx = useContext(MetaContext);
  if (!ctx) throw new Error("useMeta() πρέπει να καλείται μέσα σε <MetaProvider>.");
  return ctx;
}
