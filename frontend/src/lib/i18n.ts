import { useSyncExternalStore } from 'react'
import type { Language } from './types'

// Lightweight i18n store: Bangla / English, per report F requirement S02.
// A route or client selection never grants authorization — language is a
// display preference only.

const STORAGE_KEY = 'fieldshift.locale'
let current: Language = 'en'
const listeners = new Set<() => void>()

function emit() {
  for (const l of listeners) l()
}

export function setLocale(next: Language) {
  current = next
  try {
    localStorage.setItem(STORAGE_KEY, next)
  } catch {
    // SSR / no storage — fine, in-memory only
  }
  emit()
}

export function getLocale(): Language {
  return current
}

export function useLocale(): Language {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    () => current,
    () => 'en',
  )
}

const DICT = {
  app_name: { en: 'FieldShift', bn: 'ফিল্ডশিফট' },
  tagline: {
    en: 'Agricultural decision support',
    bn: 'কৃষি সিদ্ধান্ত সহায়ক',
  },
  nav_farmer: { en: 'Farmer', bn: 'কৃষক' },
  nav_professional: { en: 'Professional', bn: 'পেশাজীবী' },
  fields: { en: 'Fields', bn: 'জমি' },
  analyses: { en: 'Analyses', bn: 'বিশ্লেষণ' },
  cases: { en: 'Cases', bn: 'কেস' },
  rover: { en: 'Rover', bn: 'রোভার' },
  research: { en: 'Research', bn: 'গবেষণা' },
  jobs: { en: 'Jobs', bn: 'কাজ' },
  login: { en: 'Sign in', bn: 'সাইন ইন' },
  logout: { en: 'Sign out', bn: 'সাইন আউট' },
  switch_workspace: { en: 'Switch workspace', bn: 'ওয়ার্কস্পেস বদলান' },
  request_comparison: { en: 'Request comparison', bn: 'তুলনা চান' },
  baseline: { en: 'Baseline', bn: 'বেসলাইন' },
  alternative: { en: 'Alternative', bn: 'বিকল্প' },
  water_demand: { en: 'Water demand', bn: 'পানির চাহিদা' },
  heat_exposure: { en: 'Heat exposure', bn: 'তাপ প্রকাশ' },
  soil_cover: { en: 'Soil cover', bn: 'মাটি আচ্ছাদন' },
  rotation_diversity: { en: 'Rotation diversity', bn: 'ফসল চক্র বৈচিত্র্য' },
  economics: { en: 'Economics', bn: 'অর্থনীতি' },
  feasibility: { en: 'Feasibility', bn: 'সম্ভাব্যতা' },
  feasible: { en: 'Feasible', bn: 'সম্ভব' },
  constrained: { en: 'Constrained', bn: 'সীমিত' },
  infeasible: { en: 'Infeasible', bn: 'অসম্ভব' },
  status: { en: 'Status', bn: 'অবস্থা' },
  queued: { en: 'Queued', bn: 'লাইনে' },
  running: { en: 'Running', bn: 'চলমান' },
  complete: { en: 'Complete', bn: 'সম্পন্ন' },
  partial: { en: 'Partial', bn: 'আংশিক' },
  failed: { en: 'Failed', bn: 'ব্যর্থ' },
  cancelled: { en: 'Cancelled', bn: 'বাতিল' },
  open_case: { en: 'Open officer case', bn: 'অফিসার কেস খুলুন' },
  record_plan: { en: 'Record selected plan', bn: 'নির্বাচিত পরিকল্পনা নথিভুক্ত করুন' },
  evidence: { en: 'Evidence', bn: 'প্রমাণ' },
  assumptions: { en: 'Assumptions', bn: 'ধরনা' },
  missing_data: { en: 'Missing data', bn: 'অনুপস্থিত তথ্য' },
  coverage: { en: 'Coverage', bn: 'আবরণ' },
  stale: { en: 'Stale', bn: 'পুরোনো' },
  units: { en: 'Units', bn: 'একক' },
  rule_version: { en: 'Rule version', bn: 'নিয়ম সংস্করণ' },
  observations: { en: 'Observations', bn: 'পর্যবেক্ষণ' },
  request_inspection: { en: 'Request inspection', bn: 'পরিদর্শন চান' },
  export_data: { en: 'Export data', bn: 'তথ্য রপ্তানি' },
  provenance: { en: 'Provenance', bn: 'উৎস' },
  weights: { en: 'Priority weights', bn: 'অগ্রাধিকার ওজন' },
  pin_estimate: {
    en: 'Point estimate — pin only',
    bn: 'বিন্দু আনুমানিক — পিন মাত্র',
  },
  no_results: { en: 'No feasible alternatives yet', bn: 'এখনও কোনো সম্ভাব্য বিকল্প নেই' },
  insufficient: {
    en: 'Insufficient evidence to produce two alternatives. Showing the limitation rather than fabricating options.',
    bn: 'দুটি বিকল্প তৈরি করার জন্য পর্যাপ্ত প্রমাণ নেই। সীমাবদ্ধতা দেখানো হচ্ছে, বিকল্প তৈরি করা হচ্ছে না।',
  },
  disclaimer: {
    en: 'Supports decisions; does not guarantee yield, profit or soil-health improvement. Historical observations, scenarios, forecasts and rover readings are kept distinct.',
    bn: 'সিদ্ধান্ত সহায়তা করে; ফলন, লাভ বা মাটির স্বাস্থ্যের উন্নতি নিশ্চিত করে না। ইতিহাস, পরিস্থিতি, পূর্বাভাস ও রোভার পঠন পৃথক রাখা হয়।',
  },
  month_names_en: {
    en: 'Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec',
    bn: 'জানু,ফেব্রু,মার্চ,এপ্রিল,মে,জুন,জুলাই,আগ,সেপ্টে,অক্টো,নভে,ডিসে',
  },
} as const

export type DictKey = keyof typeof DICT

export function t(key: string, lang: Language = current): string {
  const entry = DICT[key as DictKey]
  return entry ? entry[lang] : key
}
