// Κοινά helpers για prospects — χρησιμοποιούνται από ProspectsScreen (Phase 2)
// και θα ξαναχρησιμοποιηθούν στο HomeScreen (Phase 4).

import type { Prospect } from "./types";

// birth_date προτεραιότητα έναντι age_manual — μια αποθηκευμένη ηλικία γίνεται
// λάθος μετά από έναν χρόνο, οπότε παράγουμε την ηλικία στο render.
export function deriveAge(p: Pick<Prospect, "birth_date" | "age_manual">): number | null {
  if (p.birth_date) {
    const today = new Date();
    const dob = new Date(p.birth_date + "T00:00:00");
    let age = today.getFullYear() - dob.getFullYear();
    const birthdayPassedThisYear =
      today.getMonth() > dob.getMonth() ||
      (today.getMonth() === dob.getMonth() && today.getDate() >= dob.getDate());
    if (!birthdayPassedThisYear) age -= 1;
    return age;
  }
  if (p.age_manual != null) return p.age_manual;
  return null;
}

export function prospectFullName(p: Pick<Prospect, "first_name" | "last_name">): string {
  return `${p.first_name} ${p.last_name}`.trim();
}

// Στοιχεία prospect που περνάνε στο SearchScreen μέσω router state (Phase 3,
// Direction 1) — ΟΧΙ query params, ώστε να μη χρειάζεται encode/parse.
export interface FromProspectPrefill {
  id: string;
  name: string;
  height_cm: number | null;
  weight_kg: number | null;
}

export function toFromProspectPrefill(
  p: Pick<Prospect, "id" | "first_name" | "last_name" | "height_cm" | "weight_kg">
): FromProspectPrefill {
  return {
    id: p.id,
    name: prospectFullName(p),
    height_cm: p.height_cm,
    weight_kg: p.weight_kg,
  };
}
