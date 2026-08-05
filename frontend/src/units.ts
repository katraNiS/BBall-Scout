// Μοναδικό σημείο μετατροπής kg→lbs — ίδιο pattern με το to_internal/to_display
// στο backend/metadata.py. Οι prospects αποθηκεύουν weight_kg, το engine's
// FEATURE_COLS χρησιμοποιεί weight_lbs.

const KG_TO_LBS = 2.20462;

export function kgToLbs(kg: number): number {
  return kg * KG_TO_LBS;
}

// Στρογγυλοποίηση στο πλησιέστερο "step" (π.χ. weight_lbs έχει step=5) και clamp
// στο [min, max] ώστε το slider να προσγειώνεται πάντα σε έγκυρη τιμή.
export function roundToStep(value: number, step: number, min: number, max: number): number {
  const rounded = Math.round(value / step) * step;
  return Math.min(max, Math.max(min, rounded));
}
