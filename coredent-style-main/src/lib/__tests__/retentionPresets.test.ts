import { describe, expect, it } from 'vitest';
import {
  DEFAULT_MAJORITY_AGE,
  DEFAULT_MINOR_RETENTION_YEARS,
  PLATFORM_RETENTION_FLOOR_YEARS,
  RETENTION_PRESETS,
  RETENTION_PRESET_OPTIONS,
  computeMinorCeiling,
  getRetentionPreset,
  hasSpecificPreset,
  US_FALLBACK_PRESET,
} from '../retentionPresets';

describe('retentionPresets', () => {
  it('never suggests below the platform floor (7y)', () => {
    for (const preset of RETENTION_PRESETS) {
      expect(
        preset.adultYears,
        `${preset.code} suggests ${preset.adultYears}y`
      ).toBeGreaterThanOrEqual(PLATFORM_RETENTION_FLOOR_YEARS);
    }
  });

  it('has unique jurisdiction codes', () => {
    const codes = RETENTION_PRESETS.map((p) => p.code);
    expect(new Set(codes).size).toBe(codes.length);
  });

  it('gives every preset a non-empty minor rule and label', () => {
    for (const preset of RETENTION_PRESETS) {
      expect(preset.label.trim().length).toBeGreaterThan(0);
      expect(preset.minorRule.trim().length).toBeGreaterThan(0);
    }
  });

  it('covers all 50 US states + DC', () => {
    const usStates = ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY'];
    for (const code of usStates) {
      const preset = getRetentionPreset(code);
      // Either a dedicated row or the US fallback — never undefined/other country.
      expect(preset.adultYears).toBeGreaterThanOrEqual(PLATFORM_RETENTION_FLOOR_YEARS);
    }
  });

  it('falls back to the US default for unknown codes', () => {
    expect(getRetentionPreset('ZZ')).toEqual(US_FALLBACK_PRESET);
    expect(getRetentionPreset(null)).toEqual(US_FALLBACK_PRESET);
    expect(getRetentionPreset(undefined)).toEqual(US_FALLBACK_PRESET);
  });

  it('hasSpecificPreset distinguishes real rows from fallback', () => {
    expect(hasSpecificPreset('CA')).toBe(true);
    expect(hasSpecificPreset('GBR')).toBe(true);
    expect(hasSpecificPreset('ZZ')).toBe(false);
    expect(hasSpecificPreset(null)).toBe(false);
  });

  it('exposes grouped dropdown options covering every preset', () => {
    const all = RETENTION_PRESET_OPTIONS.flatMap((g) => g.items);
    expect(new Set(all.map((i) => i.code)).size).toBe(RETENTION_PRESETS.length);
    expect(all.length).toBe(RETENTION_PRESETS.length);
  });

  it('computeMinorCeiling honors practice overrides (age 19 + 10y)', () => {
    // Mirrors backend _compute_minor_ceiling_utc snapshot:
    // 2010-05-20 + 19y majority + 10y retention = 2039-05-20.
    const ceiling = computeMinorCeiling(new Date(2010, 4, 20), 19, 10);
    expect(ceiling).not.toBeNull();
    expect(ceiling!.getFullYear()).toBe(2039);
    expect(ceiling!.getMonth()).toBe(4);
  });

  it('computeMinorCeiling returns null without a DOB (adult rule only)', () => {
    expect(computeMinorCeiling(null)).toBeNull();
    expect(computeMinorCeiling(undefined)).toBeNull();
    expect(computeMinorCeiling('')).toBeNull();
    expect(computeMinorCeiling(new Date('not-a-date'))).toBeNull();
  });

  it('US fallback carries conservative defaults (18 / 7)', () => {
    expect(US_FALLBACK_PRESET.majorityAge).toBe(DEFAULT_MAJORITY_AGE);
    expect(US_FALLBACK_PRESET.minorRetentionYears).toBe(DEFAULT_MINOR_RETENTION_YEARS);
  });
});
