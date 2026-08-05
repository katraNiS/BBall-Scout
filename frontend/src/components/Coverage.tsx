// Coverage — το "honest signal" του εργαλείου.
//
// Το `coverage` ενός match είναι το κλάσμα του ζητούμενου *βάρους* που είχε
// πραγματικά δεδομένα για εκείνη τη σεζόν (βλ. availability-aware masking στο
// src/similarity.py). Μικρότερο του 1 σημαίνει ότι το score υπολογίστηκε σε
// λιγότερες διαστάσεις — το UI το δείχνει αντί να το κρύψει.

export type CoverageTier = "full" | "partial" | "thin";

export function coverageTier(coverage: number): CoverageTier {
  if (coverage >= 0.85) return "full";
  if (coverage >= 0.7) return "partial";
  return "thin";
}

export function coverageClass(coverage: number): string {
  return `cov-${coverageTier(coverage)}`;
}

/**
 * Ένα κελί ανά ζητούμενο stat, γεμάτα κατ' αναλογία του coverage.
 *
 * Τα κελιά είναι σκόπιμα *τόσα όσα και τα stats που ζήτησε ο χρήστης*, όχι ένα
 * σταθερό 23: η ερώτηση που απαντά το indicator είναι "από όσα ζήτησα, πόσα
 * μετρήθηκαν πραγματικά;" — όχι "πόσα features έχει η βάση;".
 */
export default function CoverageCells({
  coverage,
  requested,
}: {
  coverage: number;
  requested: number;
}) {
  const cells = Math.max(requested, 1);
  const filled = Math.round(coverage * cells);
  const cls = coverageClass(coverage);

  return (
    <div className="cov-cells">
      {Array.from({ length: cells }, (_, i) => (
        <div key={i} className={i < filled ? cls : undefined} />
      ))}
    </div>
  );
}
