// ============================================
// CoreDent PMS - Retention Presets (jurisdiction â†’ suggested years)
// ============================================
//
// Companion to docs/DATA_RETENTION_POLICY.md Â§ 6. When a practice picks its
// jurisdiction in Settings â†’ General, these presets auto-fill the retention
// field with a defensible starting value and surface the minor-record rule.
//
// WARNING: GUIDANCE ONLY - NOT LEGAL ADVICE. Statutory minimums vary by state
// dental board and change over time. Every value here is the *commonly cited*
// conservative figure, floored at the platform minimum (7 years) so the
// documented policy and the actual purge schedule agree. Longer retention is
// always the safe direction (minimums are minimums). Verify against your
// state board / counsel before relying on this in a compliance filing.

export interface RetentionPreset {
  /** Jurisdiction code: 'CA' (state), 'US' (default), or ISO country ('IND','GBR'). */
  code: string;
  /** Dropdown label. */
  label: string;
  /** Suggested adult-record retention in years (>= platform floor of 7). */
  adultYears: number;
  /** Human-readable guidance for minor records (not machine-enforced). */
  minorRule: string;
  /** Suggested majority age used with computeMinorCeiling (default 18). */
  majorityAge: number;
  /** Suggested extra years past majority for minor records (default 7). */
  minorRetentionYears: number;
  /** Optional footnote (e.g. radiographs, claims). */
  note?: string;
}

/** Platform floor - mirrors RETENTION_ANONYMIZED_PURGE_YEARS default. */
export const PLATFORM_RETENTION_FLOOR_YEARS = 7;
/** Common majority-age default across jurisdictions. */
export const DEFAULT_MAJORITY_AGE = 18;
/** Common minor-extra-years default. */
export const DEFAULT_MINOR_RETENTION_YEARS = 7;

/**
 * US states with commonly-cited guidance. Codes not listed here fall back to
 * the US default (7-year conservative default) â€” longer retention is the safe
 * direction, so an unlisted state is never under-served by the fallback.
 */
const usStates: Array<[string, string, number, string, string?]> = [
  // [code, label, adultYears (>=7), minorRule, note?]
  ['AL', 'Alabama', 7, 'Until age 19 (majority + 1).'],
  ['AK', 'Alaska', 7, 'Until age 21 (majority + 3).'],
  ['AZ', 'Arizona', 7, '6 years after age 18.'],
  ['AR', 'Arkansas', 10, 'Until age 21.'],
  ['CA', 'California', 7, '7 years (or until age 19, whichever is later).', 'Dental Board of California guidance.'],
  ['CO', 'Colorado', 7, 'Until age 21 (majority + 3).'],
  ['CT', 'Connecticut', 7, '7 years after age 18.'],
  ['DE', 'Delaware', 7, '7 years after age 18.'],
  ['DC', 'District of Columbia', 7, 'Until age 21.'],
  ['FL', 'Florida', 7, '5 years after age 18.', 'FL adult minimum commonly cited as 5; platform floor keeps 7.'],
  ['GA', 'Georgia', 10, 'Until age 21 (majority + 3).'],
  ['HI', 'Hawaii', 7, '6 years after age 18.'],
  ['ID', 'Idaho', 7, '5 years after age 18.'],
  ['IL', 'Illinois', 10, 'Until age 21.'],
  ['IN', 'Indiana', 7, 'Until age 21 (majority + 3).'],
  ['IA', 'Iowa', 7, '7 years after age 18.'],
  ['KS', 'Kansas', 7, '5 years after age 18.'],
  ['KY', 'Kentucky', 7, '5 years after age 18.'],
  ['LA', 'Louisiana', 7, '6 years after age 18.'],
  ['ME', 'Maine', 7, 'Until age 21 (majority + 3).'],
  ['MD', 'Maryland', 7, '5 years after age 18.'],
  ['MA', 'Massachusetts', 7, 'Until age 21 (majority + 3).'],
  ['MI', 'Michigan', 7, '7 years after age 18.'],
  ['MN', 'Minnesota', 7, '7 years after age 18.'],
  ['MS', 'Mississippi', 7, '6 years after age 18.'],
  ['MO', 'Missouri', 7, '7 years after last visit; longer for minors.'],
  ['MT', 'Montana', 7, 'Until age 21 (majority + 3).'],
  ['NE', 'Nebraska', 7, '5 years after age 18.'],
  ['NV', 'Nevada', 7, '5 years after age 18; some guidance to age 21.', 'NV adult minimum commonly cited as 5; platform floor keeps 7.'],
  ['NH', 'New Hampshire', 7, 'Until age 23 (majority + 5).'],
  ['NJ', 'New Jersey', 7, 'Until age 23.'],
  ['NM', 'New Mexico', 10, 'Until age 24 (majority + 6).'],
  ['NY', 'New York', 7, '6 years after age 18.', 'NY adult minimum commonly cited as 6; platform floor keeps 7.'],
  ['NC', 'North Carolina', 7, 'Until age 21.'],
  ['ND', 'North Dakota', 7, 'Until age 21 (majority + 3).'],
  ['OH', 'Ohio', 7, 'Until age 21.'],
  ['OK', 'Oklahoma', 7, '7 years after age 18.'],
  ['OR', 'Oregon', 7, '7 years after age 18.'],
  ['PA', 'Pennsylvania', 7, 'Until age 21.'],
  ['RI', 'Rhode Island', 7, 'Until age 21 (majority + 3).'],
  ['SC', 'South Carolina', 10, 'Until age 21 (majority + 3).'],
  ['SD', 'South Dakota', 10, 'Until age 21 (majority + 3).'],
  ['TN', 'Tennessee', 10, 'Until age 21 (majority + 3).'],
  ['TX', 'Texas', 7, 'Until age 21.', 'TX adult minimum commonly cited as 5; platform floor keeps 7.'],
  ['UT', 'Utah', 7, 'Until age 21 (majority + 3).'],
  ['VT', 'Vermont', 7, 'Until age 23 (majority + 5).'],
  ['VA', 'Virginia', 7, '6 years after age 18.'],
  ['WA', 'Washington', 7, 'Until age 21.'],
  ['WV', 'West Virginia', 7, 'Until age 20 (majority + 2).'],
  ['WI', 'Wisconsin', 7, 'Until age 23 (majority + 5).'],
  ['WY', 'Wyoming', 10, 'Until age 21 (majority + 3).'],
];

/** International presets (commonly-cited national guidance). ISO alpha-3
 *  codes avoid collisions with 2-letter US state codes (CA=California vs
 *  CAN=Canada, IN=Indiana vs IND=India). */
const international: Array<[string, string, number, string, string?]> = [
  ['USA', 'United States (7-year conservative default)', 7, 'Keep until age of majority plus a conservative buffer; verify with your state board.', 'ADA guidance: at least 7 years after last treatment; longer for minors.'],
  ['IND', 'India', 7, 'Until age of majority plus a conservative buffer.', 'Clinical Establishments / NMC guidance commonly cites 3-5 years; platform floor keeps 7 (conservative).'],
  ['GBR', 'United Kingdom', 8, 'NHS guidance: until the 25th birthday for children.', 'NHS: 8 years adults; children until 25th birthday or 8 years after last entry, whichever is later.'],
  ['CAN', 'Canada', 10, '10 years after age of majority (varies by province).', 'Provincial colleges commonly cite 10 years; verify your province.'],
  ['AUS', 'Australia', 7, 'Until age 21+ (state-dependent); commonly 7 years after last visit for adults.', 'State boards vary; 7-year conservative default.'],
];

function fromTuple(t: [string, string, number, string, string?]): RetentionPreset {
  const [code, label, adultYears, minorRule, note] = t;
  return {
    code,
    label,
    adultYears,
    minorRule,
    // Most jurisdictions use 18 as the age of majority; per-state overrides
    // live in MAJORITY_AGE_OVERRIDES below (kept small to say explicit).
    majorityAge: MAJORITY_AGE_OVERRIDES[code] ?? DEFAULT_MAJORITY_AGE,
    minorRetentionYears: DEFAULT_MINOR_RETENTION_YEARS,
    note,
  };
}

// Age-18 is the US default everywhere except these (well-known exceptions).
const MAJORITY_AGE_OVERRIDES: Record<string, number> = {
  AL: 19, // Alabama: 19
  MS: 21, // Mississippi: 21
  NE: 19, // Nebraska: 19
};

export const US_FALLBACK_PRESET: RetentionPreset = fromTuple(international[0]);

/** All presets: US states first, then international (incl. the US default). */
export const RETENTION_PRESETS: RetentionPreset[] = [
  ...usStates.map(fromTuple),
  ...international.map(fromTuple),
];

/** Dropdown options, grouped for a two-column select. */
export const RETENTION_PRESET_OPTIONS: Array<{
  group: string;
  items: Array<{ code: string; label: string; adultYears: number }>;
}> = [
  {
    group: 'International',
    items: international.map(fromTuple).map((p) => ({ code: p.code, label: p.label, adultYears: p.adultYears })),
  },
  {
    group: 'US States',
    items: usStates.map(fromTuple).map((p) => ({ code: p.code, label: p.label, adultYears: p.adultYears })),
  },
];

/**
 * Resolve a jurisdiction code to its preset. Unknown / unlisted US states
 * fall back to the US 7-year conservative default (the safe direction -
 * longer retention is never the liability).
 */
export function getRetentionPreset(code: string | null | undefined): RetentionPreset {
  if (!code) return US_FALLBACK_PRESET;
  const found = RETENTION_PRESETS.find((p) => p.code === code);
  return found ?? US_FALLBACK_PRESET;
}

/**
 * True when the stored jurisdiction has its own row (vs. falling back).
 * The UI uses this to distinguish "preset applied" from "custom value".
 */
export function hasSpecificPreset(code: string | null | undefined): boolean {
  if (!code) return false;
  return RETENTION_PRESETS.some((p) => p.code === code);
}

/**
 * Compute the minor-record retention ceiling for a patient, in UTC.
 * docs/DATA_RETENTION_POLICY.md R1: not purged before
 *   date_of_birth + majority_age + minor_retention_years
 * majorityAge default 18, minorRetentionYears default 7.
 * Returns null when DOB is missing (caller applies the adult rule only,
 * the safe direction for a row that *could* be a minor).
 * This is snapshot at anonymize time as patients.purge_eligible_at so the
 * ceiling survives DOB erasure.
 */
export function computeMinorCeiling(
  dateOfBirth: Date | string | null | undefined,
  majorityAge?: number | null,
  minorRetentionYears?: number | null,
): Date | null {
  const dob = typeof dateOfBirth === 'string' ? new Date(dateOfBirth) : dateOfBirth;
  if (!dob || Number.isNaN(dob.getTime())) return null;
  const majority = majorityAge ?? 18;
  const extraYears = minorRetentionYears ?? 7;
  const ceiling = new Date(dob);
  ceiling.setFullYear(ceiling.getFullYear() + majority);
  ceiling.setFullYear(ceiling.getFullYear() + extraYears);
  return ceiling;
}

