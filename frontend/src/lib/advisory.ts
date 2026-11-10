// Advisory data — season reports, forecasts, rover field checks and SMS alerts.
// Demo/seed data only (no backend). Every string is bilingual: English is
// primary, Bangla is the farmer's other language. Season reports follow the
// model-training report format (C13_R00_C01 Kharif-II): current situation,
// what the numbers mean, satellite evidence, irrigation decision, next step,
// candidate rotations (verify locally), confidence and soil care.

export type LangText = { en: string; bn: string }

export type Confidence = 'high' | 'medium' | 'low'

export interface RotationSuggestion {
  title: LangText
  waterNeed: 'low' | 'medium' | 'high'
  suitability: number // 0-1
  why: LangText
  risk: LangText
}

export interface SeasonWarning {
  level: 'info' | 'warn' | 'danger'
  text: LangText
}

export interface SeasonReport {
  id: string
  fieldId: string
  fieldName: string
  season: LangText
  date: string
  currentSituation: LangText
  numbersMean: LangText
  evidence: LangText
  irrigationDecision: LangText
  irrigationLevel: 'ok' | 'insufficient' | 'watch'
  nextStep: LangText
  rotations: RotationSuggestion[]
  rotationNote: LangText
  note: LangText
  confidence: Confidence
  confidenceReason: LangText
  soilCare: LangText
  warnings: SeasonWarning[]
}

export const SEASON_REPORTS: SeasonReport[] = [
  {
    id: 'sr-f1-kharif2',
    fieldId: 'f-1',
    fieldName: 'North paddy plot',
    season: { en: 'Kharif-II season report', bn: 'খরিফ-২ মৌসুমের প্রতিবেদন' },
    date: '2026-10-20',
    currentSituation: {
      en: 'Vegetation has declined; soil moisture is moderate.',
      bn: 'গাছপালা কমেছে, মাটির আর্দ্রতা মাঝারি।',
    },
    numbersMean: {
      en: 'NDVI is a greenness score from 0 to 1 (higher = greener). Soil moisture is the amount of water per cubic metre of soil (m³/m³). “Anomaly” means how far the value is from normal for this time of year.',
      bn: 'NDVI হলো সবুজের একটি স্কোর (০ থেকে ১; বেশি মানে বেশি সবুজ)। মাটির আর্দ্রতা মানে মাটির প্রতি ঘনমিটারে পানির পরিমাণ (m³/m³)। “স্বাভাবিকের চেয়ে” মানে এই সময়ের স্বাভাবিক মানের তুলনায় কতটা কম বা বেশি।',
    },
    evidence: {
      en: 'NDVI 0.42 (anomaly −0.138); satellite soil moisture 0.22 m³/m³ (anomaly z −0.09); last clear observation 2026-10-20. Note: soil moisture covers about 3 km from the satellite, not a direct measurement of your 1 km cell.',
      bn: 'NDVI ০.৪২ (স্বাভাবিকের চেয়ে −০.১৩৮); মাটির আর্দ্রতা ০.২২ m³/m³ (স্বাভাবিকের চেয়ে −০.০৯); শেষ পরিষ্কার পর্যবেক্ষণ 2026-10-20। মনে রাখবেন: আর্দ্রতার তথ্য উপগ্রহের প্রায় ৩ কিমি এলাকার, আপনার ১ কিমি জমির সরাসরি মাপ নয়।',
    },
    irrigationDecision: {
      en: 'Insufficient evidence for a reliable recommendation.',
      bn: 'নির্ভরযোগ্য পরামর্শের জন্য পর্যাপ্ত তথ্য নেই।',
    },
    irrigationLevel: 'insufficient',
    nextStep: {
      en: 'Cloud or missing data means no reliable advice can be given yet. Wait for the next clear observation.',
      bn: 'মেঘ বা তথ্যের ঘাটতির কারণে নির্ভরযোগ্য পরামর্শ দেওয়া যাচ্ছে না। পরের পরিষ্কার পর্যবেক্ষণের জন্য অপেক্ষা করুন।',
    },
    rotations: [
      {
        title: {
          en: 'Kharif-II T. Aman → Rabi pulses / lentil → Kharif-I green manure / fallow',
          bn: 'খরিফ-২ আমন → রবি ডাল / মসুর → খরিফ-১ সবুজ সার / পতিত',
        },
        waterNeed: 'low',
        suitability: 0.7,
        why: {
          en: 'Low water need; legumes and fallow rebuild organic matter.',
          bn: 'কম পানি লাগে; ডাল ও পতিত জমি মাটির জৈববস্তু বাড়ায়।',
        },
        risk: {
          en: 'Lower Rabi cash output; fallow needs weed management.',
          bn: 'রবিতে নগদ ফসল কম হবে; পতিত জমিতে আগাছা নিয়ন্ত্রণ করতে হবে।',
        },
      },
      {
        title: {
          en: 'Kharif-II T. Aman → Rabi wheat / mustard / pulses → Kharif-I Aus / jute',
          bn: 'খরিফ-২ আমন → রবি গম / সরিষা / ডাল → খরিফ-১ আউশ / পাট',
        },
        waterNeed: 'medium',
        suitability: 0.6,
        why: {
          en: 'Clayey soil holds water, suitable for transplanted rice.',
          bn: 'এঁটেল মাটি পানি ধরে রাখে, রোপা ধানের জন্য উপযোগী।',
        },
        risk: {
          en: 'Rabi crop choice must match residual moisture and local markets.',
          bn: 'রবি ফসল বাছতে মাটির অবশিষ্ট আর্দ্রতা ও স্থানীয় বাজার যাচাই করা জরুরি।',
        },
      },
    ],
    rotationNote: {
      en: 'These are candidate rotations, not a yield guarantee. Check your local soil, water and market before deciding.',
      bn: 'এগুলো সম্ভাব্য ফসল চক্র, ফলনের নিশ্চয়তা নয়। সিদ্ধান্তের আগে নিজের মাটি, পানি ও বাজার যাচাই করুন।',
    },
    note: {
      en: 'Satellites cannot tell you the crop variety, sowing date or fertiliser amount. Test your soil before applying fertiliser.',
      bn: 'উপগ্রহের ছবি ফসলের জাত, বপনের তারিখ বা সারের পরিমাণ বলতে পারে না। সার দেওয়ার আগে মাটি পরীক্ষা করুন।',
    },
    confidence: 'low',
    confidenceReason: {
      en: 'Few clear pixels. If confidence is low, treat the advice with caution.',
      bn: 'পরিষ্কার পর্যবেক্ষণ কম। আস্থা কম হলে সতর্কতার সঙ্গে পরামর্শ অনুসরণ করুন।',
    },
    soilCare: {
      en: 'Keep ground cover, mix crop residues into the soil, and avoid unnecessary irrigation. Test your soil before applying fertiliser — satellites cannot give exact nitrogen, phosphorus, potassium or pH values.',
      bn: 'জমিতে আবরণ রাখুন (খড়/সবুজ সার), মাটির জৈববস্তু বাড়ান, অপ্রয়োজনীয় সেচ এড়িয়ে চলুন। নির্দিষ্ট সার সুপারিশের আগে মাটি পরীক্ষা করতে হবে — উপগ্রহের তথ্য থেকে নাইট্রোজেন, ফসফরাস, পটাশ বা pH-এর সঠিক মান বলা যায় না।',
    },
    warnings: [
      {
        level: 'warn',
        text: {
          en: 'Vegetation is below normal for this time of year (NDVI anomaly −0.138).',
          bn: 'এই সময়ের তুলনায় গাছপালা স্বাভাবিকের চেয়ে কম (NDVI −০.১৩৮)।',
        },
      },
      {
        level: 'info',
        text: {
          en: 'Confidence is LOW — few clear satellite pixels. Treat this advice with caution.',
          bn: 'আস্থা কম — পরিষ্কার উপগ্রহ ছবি কম। সতর্কতার সঙ্গে পরামর্শ নিন।',
        },
      },
    ],
  },
  {
    id: 'sr-f2-kharif2',
    fieldId: 'f-2',
    fieldName: 'River-bend plot',
    season: { en: 'Kharif-II season report', bn: 'খরিফ-২ মৌসুমের প্রতিবেদন' },
    date: '2026-10-20',
    currentSituation: {
      en: 'Vegetation is steady near the river bend; soil moisture is good.',
      bn: 'নদীর বাঁকের কাছে গাছপালা স্থিতিশীল; মাটির আর্দ্রতা ভালো।',
    },
    numbersMean: {
      en: 'NDVI is a greenness score from 0 to 1 (higher = greener). Soil moisture is the amount of water per cubic metre of soil (m³/m³). “Anomaly” means how far the value is from normal for this time of year.',
      bn: 'NDVI হলো সবুজের একটি স্কোর (০ থেকে ১; বেশি মানে বেশি সবুজ)। মাটির আর্দ্রতা মানে মাটির প্রতি ঘনমিটারে পানির পরিমাণ (m³/m³)। “স্বাভাবিকের চেয়ে” মানে এই সময়ের স্বাভাবিক মানের তুলনায় কতটা কম বা বেশি।',
    },
    evidence: {
      en: 'NDVI 0.55 (anomaly +0.04); satellite soil moisture 0.31 m³/m³ (anomaly z +0.06); last clear observation 2026-10-20. Note: soil moisture covers about 3 km from the satellite, not a direct measurement of your 1 km cell.',
      bn: 'NDVI ০.৫৫ (স্বাভাবিকের চেয়ে +০.০৪); মাটির আর্দ্রতা ০.৩১ m³/m³ (স্বাভাবিকের চেয়ে +০.০৬); শেষ পরিষ্কার পর্যবেক্ষণ 2026-10-20। মনে রাখবেন: আর্দ্রতার তথ্য উপগ্রহের প্রায় ৩ কিমি এলাকার, আপনার ১ কিমি জমির সরাসরি মাপ নয়।',
    },
    irrigationDecision: {
      en: 'Moisture is adequate for now. Watch the next 7 days — if no rain, plan one light irrigation before Rabi sowing.',
      bn: 'আপাতত আর্দ্রতা যথেষ্ট। আগামী ৭ দিন লক্ষ্য করুন — বৃষ্টি না হলে রবি বপনের আগে একবার হালকা সেচের পরিকল্পনা করুন।',
    },
    irrigationLevel: 'ok',
    nextStep: {
      en: 'Keep the current crop until harvest, then prepare the field for Rabi. Check the 7-day forecast below before sowing.',
      bn: 'ফসল কাটা পর্যন্ত বর্তমান ফসল রাখুন, তারপর রবির জন্য জমি তৈরি করুন। বপনের আগে নিচের ৭ দিনের পূর্বাভাস দেখুন।',
    },
    rotations: [
      {
        title: {
          en: 'Kharif-II T. Aman → Rabi mustard / lentil → Kharif-I Aus',
          bn: 'খরিফ-২ আমন → রবি সরিষা / মসুর → খরিফ-১ আউশ',
        },
        waterNeed: 'medium',
        suitability: 0.78,
        why: {
          en: 'Good residual moisture near the river; mustard and lentil use less water than wheat.',
          bn: 'নদীর কাছে মাটিতে আর্দ্রতা ভালো থাকে; সরিষা ও মসুর গমের চেয়ে কম পানি খায়।',
        },
        risk: {
          en: 'River-bend soil can stay wet — avoid waterlogging at sowing.',
          bn: 'নদীর বাঁকের মাটি ভেজা থাকতে পারে — বপনের সময় জলাবদ্ধতা এড়ান।',
        },
      },
      {
        title: {
          en: 'Kharif-II T. Aman → Rabi wheat → Kharif-I jute',
          bn: 'খরিফ-২ আমন → রবি গম → খরিফ-১ পাট',
        },
        waterNeed: 'medium',
        suitability: 0.65,
        why: {
          en: 'Sandy-loam drains well; wheat suits the field and jute fits the Kharif-I slot.',
          bn: 'বেলে-দোআঁশ মাটিতে পানি জমে না; গম এই জমিতে ভালো হয়, আর খরিফ-১ এ পাট মানায়।',
        },
        risk: {
          en: 'Wheat needs one irrigation if the dry spell continues.',
          bn: 'শুষ্ক আবহাওয়া চলতে থাকলে গমে একবার সেচ লাগতে পারে।',
        },
      },
    ],
    rotationNote: {
      en: 'These are candidate rotations, not a yield guarantee. Check your local soil, water and market before deciding.',
      bn: 'এগুলো সম্ভাব্য ফসল চক্র, ফলনের নিশ্চয়তা নয়। সিদ্ধান্তের আগে নিজের মাটি, পানি ও বাজার যাচাই করুন।',
    },
    note: {
      en: 'Satellites cannot tell you the crop variety, sowing date or fertiliser amount. Test your soil before applying fertiliser.',
      bn: 'উপগ্রহের ছবি ফসলের জাত, বপনের তারিখ বা সারের পরিমাণ বলতে পারে না। সার দেওয়ার আগে মাটি পরীক্ষা করুন।',
    },
    confidence: 'medium',
    confidenceReason: {
      en: 'Mostly clear pixels, but the river edge can confuse the satellite reading.',
      bn: 'বেশিরভাগ ছবি পরিষ্কার, তবে নদীর কিনারা উপগ্রহের মাপে ভুল করতে পারে।',
    },
    soilCare: {
      en: 'Keep ground cover, mix crop residues into the soil, and avoid unnecessary irrigation. Test your soil before applying fertiliser — satellites cannot give exact nitrogen, phosphorus, potassium or pH values.',
      bn: 'জমিতে আবরণ রাখুন (খড়/সবুজ সার), মাটির জৈববস্তু বাড়ান, অপ্রয়োজনীয় সেচ এড়িয়ে চলুন। নির্দিষ্ট সার সুপারিশের আগে মাটি পরীক্ষা করতে হবে — উপগ্রহের তথ্য থেকে নাইট্রোজেন, ফসফরাস, পটাশ বা pH-এর সঠিক মান বলা যায় না।',
    },
    warnings: [
      {
        level: 'info',
        text: {
          en: 'River-bend soil stays wet after rain — check drainage before Rabi sowing.',
          bn: 'বৃষ্টির পর নদীর বাঁকের মাটি ভেজা থাকে — রবি বপনের আগে পানি নিষ্কাশন দেখুন।',
        },
      },
    ],
  },
  {
    id: 'sr-f3-kharif2',
    fieldId: 'f-3',
    fieldName: 'Pin estimate — east slope',
    season: { en: 'Kharif-II season report', bn: 'খরিফ-২ মৌসুমের প্রতিবেদন' },
    date: '2026-10-20',
    currentSituation: {
      en: 'Vegetation is sparse on the east slope; soil moisture is low. This field is rainfed — there is no irrigation source.',
      bn: 'পূর্ব ঢালে গাছপালা কম; মাটির আর্দ্রতা কম। এই জমিতে সেচের ব্যবস্থা নেই — বৃষ্টির ওপর নির্ভরশীল।',
    },
    numbersMean: {
      en: 'NDVI is a greenness score from 0 to 1 (higher = greener). Soil moisture is the amount of water per cubic metre of soil (m³/m³). “Anomaly” means how far the value is from normal for this time of year.',
      bn: 'NDVI হলো সবুজের একটি স্কোর (০ থেকে ১; বেশি মানে বেশি সবুজ)। মাটির আর্দ্রতা মানে মাটির প্রতি ঘনমিটারে পানির পরিমাণ (m³/m³)। “স্বাভাবিকের চেয়ে” মানে এই সময়ের স্বাভাবিক মানের তুলনায় কতটা কম বা বেশি।',
    },
    evidence: {
      en: 'NDVI 0.38 (anomaly −0.21); satellite soil moisture 0.18 m³/m³ (anomaly z −0.15); last clear observation 2026-10-20. This is a pin estimate from a small slope plot — the satellite value is approximate.',
      bn: 'NDVI ০.৩৮ (স্বাভাবিকের চেয়ে −০.২১); মাটির আর্দ্রতা ০.১৮ m³/m³ (স্বাভাবিকের চেয়ে −০.১৫); শেষ পরিষ্কার পর্যবেক্ষণ 2026-10-20। এটি ছোট ঢালু জমির আনুমানিক হিসাব — উপগ্রহের মানটি মোটামুটি।',
    },
    irrigationDecision: {
      en: 'No irrigation source on this field. Rely on rainfall and mulch to hold moisture.',
      bn: 'এই জমিতে সেচের উৎস নেই। বৃষ্টি ও খড়ের আবরণ দিয়ে আর্দ্রতা ধরে রাখুন।',
    },
    irrigationLevel: 'watch',
    nextStep: {
      en: 'Mulch the slope now to slow moisture loss, and choose a drought-tolerant Rabi crop. Wait for rain before sowing.',
      bn: 'এখনই ঢালে খড়ের আবরণ দিন যাতে আর্দ্রতা কম না যায়, এবং খরা-সহনশীল রবি ফসল বাছুন। বপনের আগে বৃষ্টির অপেক্ষা করুন।',
    },
    rotations: [
      {
        title: {
          en: 'Kharif-II T. Aman → Rabi chickpea / lentil → Kharif-I fallow',
          bn: 'খরিফ-২ আমন → রবি ছোলা / মসুর → খরিফ-১ পতিত',
        },
        waterNeed: 'low',
        suitability: 0.72,
        why: {
          en: 'Chickpea and lentil survive on residual moisture; they need almost no irrigation.',
          bn: 'ছোলা ও মসুর মাটির অবশিষ্ট আর্দ্রতায় বাঁচে; প্রায় সেচ লাগে না।',
        },
        risk: {
          en: 'Yields are modest on a slope; mulch is essential to hold moisture.',
          bn: 'ঢালে ফলন মাঝারি হয়; আর্দ্রতা ধরে রাখতে খড়ের আবরণ জরুরি।',
        },
      },
      {
        title: {
          en: 'Kharif-II T. Aman → Rabi mustard → Kharif-I green manure',
          bn: 'খরিফ-২ আমন → রবি সরিষা → খরিফ-১ সবুজ সার',
        },
        waterNeed: 'low',
        suitability: 0.58,
        why: {
          en: 'Mustard is short-duration and drought-tolerant; green manure rebuilds slope soil.',
          bn: 'সরিষা অল্প দিনের ও খরা-সহনশীল; সবুজ সার ঢালের মাটি ভালো করে।',
        },
        risk: {
          en: 'If the dry spell continues, even mustard may need one watering.',
          bn: 'শুষ্ক আবহাওয়া চলতে থাকলে সরিষাতেও একবার পানি লাগতে পারে।',
        },
      },
    ],
    rotationNote: {
      en: 'These are candidate rotations, not a yield guarantee. Check your local soil, water and market before deciding.',
      bn: 'এগুলো সম্ভাব্য ফসল চক্র, ফলনের নিশ্চয়তা নয়। সিদ্ধান্তের আগে নিজের মাটি, পানি ও বাজার যাচাই করুন।',
    },
    note: {
      en: 'Satellites cannot tell you the crop variety, sowing date or fertiliser amount. Test your soil before applying fertiliser.',
      bn: 'উপগ্রহের ছবি ফসলের জাত, বপনের তারিখ বা সারের পরিমাণ বলতে পারে না। সার দেওয়ার আগে মাটি পরীক্ষা করুন।',
    },
    confidence: 'low',
    confidenceReason: {
      en: 'Pin estimate on a small slope plot — few pixels and a rough boundary.',
      bn: 'ছোট ঢালু জমির আনুমানিক হিসাব — ছবির পিক্সেল কম, সীমানাও মোটামুটি।',
    },
    soilCare: {
      en: 'Mulch the slope, keep ground cover, and avoid unnecessary irrigation. Test your soil before applying fertiliser — satellites cannot give exact nitrogen, phosphorus, potassium or pH values.',
      bn: 'ঢালে খড়ের আবরণ দিন, জমিতে আবরণ রাখুন, অপ্রয়োজনীয় সেচ এড়িয়ে চলুন। নির্দিষ্ট সার সুপারিশের আগে মাটি পরীক্ষা করতে হবে — উপগ্রহের তথ্য থেকে নাইট্রোজেন, ফসফরাস, পটাশ বা pH-এর সঠিক মান বলা যায় না।',
    },
    warnings: [
      {
        level: 'warn',
        text: {
          en: 'Soil moisture is well below normal (anomaly −0.15). Drought-tolerant Rabi crops only.',
          bn: 'মাটির আর্দ্রতা স্বাভাবিকের চেয়ে অনেক কম (−০.১৫)। শুধু খরা-সহনশীল রবি ফসল বাছুন।',
        },
      },
      {
        level: 'danger',
        text: {
          en: 'No irrigation source on this field. If no rain falls in the next 10 days, delay Rabi sowing.',
          bn: 'এই জমিতে সেচের উৎস নেই। আগামী ১০ দিনে বৃষ্টি না হলে রবি বপন পিছিয়ে দিন।',
        },
      },
    ],
  },
]

export function getSeasonReport(fieldId: string): SeasonReport | undefined {
  return SEASON_REPORTS.find((r) => r.fieldId === fieldId)
}

// --- Forecasts ---------------------------------------------------------------

export interface ForecastDay {
  date: string
  rainMm: number
  tempMaxC: number
  tempMinC: number
  condition: LangText
  advice: LangText
}

export interface SeasonForecast {
  fieldId: string
  season: LangText
  outlook: LangText
  days: ForecastDay[]
}

export const FORECASTS: SeasonForecast[] = [
  {
    fieldId: 'f-1',
    season: { en: 'Rabi outlook — North paddy plot', bn: 'রবি পূর্বাভাস — উত্তর ধান প্লট' },
    outlook: {
      en: 'A dry spell is expected for the next 10 days, with light rain possible around 16 Nov. Day temperatures 29–31°C, nights 19–21°C. Good sowing window for lentil and mustard opens after the rain; hold off sowing until the soil is moist.',
      bn: 'আগামী ১০ দিন শুষ্ক থাকবে বলে আশা করা হচ্ছে, ৩০ অক্টোবরের দিকে হালকা বৃষ্টি হতে পারে। দিনে ২৯–৩১°সে, রাতে ১৯–২১°সে। বৃষ্টির পর মসুর ও সরিষা বপনের ভালো সময় আসবে; মাটি ভেজা না হওয়া পর্যন্ত বপন থামিয়ে রাখুন।',
    },
    days: [
      { date: '2026-11-11', rainMm: 0, tempMaxC: 31, tempMinC: 21, condition: { en: 'Sunny', bn: 'রোদ' }, advice: { en: 'Dry — good for harvest work.', bn: 'শুষ্ক — ফসল কাটার কাজের জন্য ভালো।' } },
      { date: '2026-11-12', rainMm: 0, tempMaxC: 31, tempMinC: 20, condition: { en: 'Sunny', bn: 'রোদ' }, advice: { en: 'Dry — keep straw cover on the field.', bn: 'শুষ্ক — জমিতে খড়ের আবরণ রাখুন।' } },
      { date: '2026-11-13', rainMm: 2, tempMaxC: 30, tempMinC: 20, condition: { en: 'Light showers', bn: 'হালকা বৃষ্টি' }, advice: { en: 'Light rain — helps moisture, not enough to sow.', bn: 'হালকা বৃষ্টি — আর্দ্রতা বাড়বে, বপনের জন্য যথেষ্ট নয়।' } },
      { date: '2026-11-14', rainMm: 0, tempMaxC: 30, tempMinC: 19, condition: { en: 'Partly cloudy', bn: 'আংশিক মেঘলা' }, advice: { en: 'Cloudy — prepare seedbeds.', bn: 'মেঘলা — বীজতলা তৈরি করুন।' } },
      { date: '2026-11-15', rainMm: 0, tempMaxC: 29, tempMinC: 19, condition: { en: 'Sunny', bn: 'রোদ' }, advice: { en: 'Dry — mulch the field edges.', bn: 'শুষ্ক — জমির কিনারায় খড় দিন।' } },
      { date: '2026-11-16', rainMm: 0, tempMaxC: 30, tempMinC: 20, condition: { en: 'Sunny', bn: 'রোদ' }, advice: { en: 'Dry — check stored seed for Rabi.', bn: 'শুষ্ক — রবির বীজ পরীক্ষা করুন।' } },
      { date: '2026-11-17', rainMm: 4, tempMaxC: 29, tempMinC: 20, condition: { en: 'Rain likely', bn: 'বৃষ্টি হতে পারে' }, advice: { en: 'Rain likely — a good sowing window opens after this.', bn: 'বৃষ্টি হতে পারে — এরপর বপনের ভালো সময় আসবে।' } },
    ],
  },
  {
    fieldId: 'f-2',
    season: { en: 'Rabi outlook — River-bend plot', bn: 'রবি পূর্বাভাস — নদীর বাঁকের প্লট' },
    outlook: {
      en: 'River-bend soil holds moisture well, so the dry spell matters less here. Light rain around 13 Nov and 17 Nov. Day 29–31°C, nights 19–21°C. Mustard and lentil can be sown after 14 Nov; watch drainage if rain is heavy.',
      bn: 'নদীর বাঁকের মাটি আর্দ্রতা ভালো ধরে রাখে, তাই শুষ্ক আবহাওয়া এখানে কম সমস্যা। ২৩ ও ২৭ অক্টোবর হালকা বৃষ্টি হতে পারে। দিনে ২৯–৩১°সে, রাতে ১৯–২১°সে। ২৪ অক্টোবরের পর সরিষা ও মসুর বপন করা যাবে; ভারী বৃষ্টি হলে পানি নিষ্কাশন দেখুন।',
    },
    days: [
      { date: '2026-11-11', rainMm: 0, tempMaxC: 31, tempMinC: 21, condition: { en: 'Sunny', bn: 'রোদ' }, advice: { en: 'Dry — river moisture helps.', bn: 'শুষ্ক — নদীর আর্দ্রতা সাহায্য করবে।' } },
      { date: '2026-11-12', rainMm: 1, tempMaxC: 31, tempMinC: 20, condition: { en: 'Light showers', bn: 'হালকা বৃষ্টি' }, advice: { en: 'Light rain — soil stays moist.', bn: 'হালকা বৃষ্টি — মাটি ভেজা থাকবে।' } },
      { date: '2026-11-13', rainMm: 3, tempMaxC: 30, tempMinC: 20, condition: { en: 'Light showers', bn: 'হালকা বৃষ্টি' }, advice: { en: 'Rain — good for mustard seedbed.', bn: 'বৃষ্টি — সরিষার বীজতলার জন্য ভালো।' } },
      { date: '2026-11-14', rainMm: 0, tempMaxC: 30, tempMinC: 19, condition: { en: 'Partly cloudy', bn: 'আংশিক মেঘলা' }, advice: { en: 'Sowing window opens for mustard.', bn: 'সরিষা বপনের সময় এসেছে।' } },
      { date: '2026-11-15', rainMm: 0, tempMaxC: 29, tempMinC: 19, condition: { en: 'Sunny', bn: 'রোদ' }, advice: { en: 'Dry — sow lentil now.', bn: 'শুষ্ক — এখন মসুর বুনুন।' } },
      { date: '2026-11-16', rainMm: 0, tempMaxC: 30, tempMinC: 20, condition: { en: 'Sunny', bn: 'রোদ' }, advice: { en: 'Dry — check drainage channels.', bn: 'শুষ্ক — পানি নিষ্কাশনের নালা দেখুন।' } },
      { date: '2026-11-17', rainMm: 5, tempMaxC: 29, tempMinC: 20, condition: { en: 'Rain likely', bn: 'বৃষ্টি হতে পারে' }, advice: { en: 'Rain likely — avoid sowing on wet beds.', bn: 'বৃষ্টি হতে পারে — ভেজা বীজতলায় বপন করবেন না।' } },
    ],
  },
  {
    fieldId: 'f-3',
    season: { en: 'Rabi outlook — East slope (pin estimate)', bn: 'রবি পূর্বাভাস — পূর্ব ঢাল (আনুমানিক)' },
    outlook: {
      en: 'The slope dries fast. Only 6 mm of rain is expected in the next 7 days. Day 29–31°C, nights 19–21°C. Do not sow before rain — mulch now and wait for the 17 Nov rain before sowing chickpea or lentil.',
      bn: 'ঢাল দ্রুত শুকিয়ে যায়। আগামী ৭ দিনে মাত্র ৬ মিমি বৃষ্টি আশা করা হচ্ছে। দিনে ২৯–৩১°সে, রাতে ১৯–২১°সে। বৃষ্টির আগে বপন করবেন না — এখনই খড় দিন এবং ২৭ অক্টোবরের বৃষ্টির পর ছোলা বা মসুর বুনুন।',
    },
    days: [
      { date: '2026-11-11', rainMm: 0, tempMaxC: 31, tempMinC: 21, condition: { en: 'Sunny', bn: 'রোদ' }, advice: { en: 'Dry — mulch the slope today.', bn: 'শুষ্ক — আজই ঢালে খড় দিন।' } },
      { date: '2026-11-12', rainMm: 0, tempMaxC: 31, tempMinC: 20, condition: { en: 'Sunny', bn: 'রোদ' }, advice: { en: 'Dry — do not sow yet.', bn: 'শুষ্ক — এখনো বপন করবেন না।' } },
      { date: '2026-11-13', rainMm: 1, tempMaxC: 30, tempMinC: 20, condition: { en: 'Light showers', bn: 'হালকা বৃষ্টি' }, advice: { en: 'Too little rain to sow.', bn: 'বপনের জন্য বৃষ্টি যথেষ্ট নয়।' } },
      { date: '2026-11-14', rainMm: 0, tempMaxC: 30, tempMinC: 19, condition: { en: 'Partly cloudy', bn: 'আংশিক মেঘলা' }, advice: { en: 'Dry — keep mulch in place.', bn: 'শুষ্ক — খড়ের আবরণ ঠিক রাখুন।' } },
      { date: '2026-11-15', rainMm: 0, tempMaxC: 29, tempMinC: 19, condition: { en: 'Sunny', bn: 'রোদ' }, advice: { en: 'Dry — prepare chickpea seed.', bn: 'শুষ্ক — ছোলার বীজ তৈরি রাখুন।' } },
      { date: '2026-11-16', rainMm: 0, tempMaxC: 30, tempMinC: 20, condition: { en: 'Sunny', bn: 'রোদ' }, advice: { en: 'Dry — wait for rain.', bn: 'শুষ্ক — বৃষ্টির অপেক্ষা করুন।' } },
      { date: '2026-11-17', rainMm: 5, tempMaxC: 29, tempMinC: 20, condition: { en: 'Rain likely', bn: 'বৃষ্টি হতে পারে' }, advice: { en: 'Rain likely — sow chickpea after this rain.', bn: 'বৃষ্টি হতে পারে — এই বৃষ্টির পর ছোলা বুনুন।' } },
    ],
  },
]

export function getForecast(fieldId: string): SeasonForecast | undefined {
  return FORECASTS.find((f) => f.fieldId === fieldId)
}

// --- Rover field checks ------------------------------------------------------

export interface RoverThreat {
  type: LangText
  severity: 'low' | 'medium' | 'high'
  note: LangText
}

export interface RoverDisease {
  name: LangText
  severity: 'low' | 'medium' | 'high'
  note: LangText
}

export interface RoverCheck {
  id: string
  fieldId: string
  fieldName: string
  deviceId: string
  deviceName: string
  checkedAt: string
  nutrition: { nPpm: number; pPpm: number; kPpm: number; level: LangText }
  moisturePct: number
  tempC: number
  cropHealth: { score: number; note: LangText; cameraNote: LangText }
  threats: RoverThreat[]
  diseases: RoverDisease[]
}

export const ROVER_CHECKS: RoverCheck[] = [
  {
    id: 'rc-f1',
    fieldId: 'f-1',
    fieldName: 'North paddy plot',
    deviceId: 'rover-1',
    deviceName: 'FS-Rover 01',
    checkedAt: '2026-10-20T09:40:00Z',
    nutrition: { nPpm: 18, pPpm: 11, kPpm: 132, level: { en: 'Nitrogen low, potassium adequate', bn: 'নাইট্রোজেন কম, পটাশ যথেষ্ট' } },
    moisturePct: 22,
    tempC: 29.4,
    cropHealth: {
      score: 0.62,
      note: { en: 'Crop looks thin in the north corner; leaves are pale.', bn: 'উত্তর কোণে ফসল পাতলা; পাতা ফ্যাকাশে।' },
      cameraNote: { en: 'Camera: 42 photos analysed — canopy cover 58%, yellowing on older leaves.', bn: 'ক্যামেরা: ৪২টি ছবি বিশ্লেষণ — গাছের আবরণ ৫৮%, পুরনো পাতায় হলদে ভাব।' },
    },
    threats: [
      { type: { en: 'Brown planthopper', bn: 'বাদামি গাছফড়িং' }, severity: 'medium', note: { en: 'Small numbers on lower stems. Check again in 5 days.', bn: 'নিচের কাণ্ডে অল্প সংখ্যায়। ৫ দিন পর আবার দেখুন।' } },
      { type: { en: 'Stem borer (moth)', bn: 'মাজরা পোকা' }, severity: 'low', note: { en: 'Few moths seen at dusk. No action needed yet.', bn: 'সন্ধ্যায় অল্প মথ দেখা গেছে। এখনো কিছু করার দরকার নেই।' } },
    ],
    diseases: [
      { name: { en: 'Bacterial leaf blight — early signs', bn: 'ব্যাকটেরিয়াজনিত পাতা পোড়া — প্রাথমিক লক্ষণ' }, severity: 'low', note: { en: 'Water-soaked spots on 3–4 leaves. Remove affected leaves.', bn: '৩–৪টি পাতায় পানিভেজা দাগ। আক্রান্ত পাতা তুলে ফেলুন।' } },
    ],
  },
  {
    id: 'rc-f2',
    fieldId: 'f-2',
    fieldName: 'River-bend plot',
    deviceId: 'rover-2',
    deviceName: 'FS-Rover 02',
    checkedAt: '2026-10-19T15:20:00Z',
    nutrition: { nPpm: 26, pPpm: 14, kPpm: 148, level: { en: 'Balanced — nitrogen and potassium adequate', bn: 'ভারসাম্যপূর্ণ — নাইট্রোজেন ও পটাশ যথেষ্ট' } },
    moisturePct: 31,
    tempC: 28.1,
    cropHealth: {
      score: 0.78,
      note: { en: 'Crop is dense and green; good tillering.', bn: 'ফসল ঘন ও সবুজ; কুশি ভালো।' },
      cameraNote: { en: 'Camera: 38 photos analysed — canopy cover 81%, no yellowing.', bn: 'ক্যামেরা: ৩৮টি ছবি বিশ্লেষণ — গাছের আবরণ ৮১%, হলদে ভাব নেই।' },
    },
    threats: [
      { type: { en: 'Rice hispa (beetle)', bn: 'হিসপা পোকা' }, severity: 'low', note: { en: 'A few beetles on leaf edges. Monitor only.', bn: 'পাতার কিনারায় অল্প পোকা। শুধু নজর রাখুন।' } },
    ],
    diseases: [],
  },
  {
    id: 'rc-f3',
    fieldId: 'f-3',
    fieldName: 'Pin estimate — east slope',
    deviceId: 'rover-1',
    deviceName: 'FS-Rover 01',
    checkedAt: '2026-10-18T11:05:00Z',
    nutrition: { nPpm: 12, pPpm: 8, kPpm: 96, level: { en: 'Nitrogen and phosphorus low — slope soil is thin', bn: 'নাইট্রোজেন ও ফসফরাস কম — ঢালের মাটি পাতলা' } },
    moisturePct: 18,
    tempC: 30.2,
    cropHealth: {
      score: 0.48,
      note: { en: 'Crop is sparse and stressed by dry soil.', bn: 'ফসল কম ও শুষ্ক মাটিতে চাপে আছে।' },
      cameraNote: { en: 'Camera: 24 photos analysed — canopy cover 41%, dry patches on the slope.', bn: 'ক্যামেরা: ২৪টি ছবি বিশ্লেষণ — গাছের আবরণ ৪১%, ঢালে শুষ্ক জায়গা।' },
    },
    threats: [
      { type: { en: 'Cutworm', bn: 'কাটুই পোকা' }, severity: 'medium', note: { en: 'Cut seedlings found near the field edge. Hand-pick at night.', bn: 'জমির কিনারায় কাটা চারা পাওয়া গেছে। রাতে হাতে তুলুন।' } },
    ],
    diseases: [
      { name: { en: 'Sheath blight — small patches', bn: 'খোলপচা — ছোট ছোট দাগ' }, severity: 'medium', note: { en: 'Lesions on lower sheaths. Avoid excess nitrogen; improve drainage.', bn: 'নিচের খোলে দাগ। বেশি নাইট্রোজেন দেবেন না; পানি নিষ্কাশন ভালো করুন।' } },
    ],
  },
]

export function getRoverCheck(fieldId: string): RoverCheck | undefined {
  return ROVER_CHECKS.find((r) => r.fieldId === fieldId)
}

// --- SMS alerts --------------------------------------------------------------
// Demo log of the messages that would be sent automatically to a farmer's
// phone when they cannot check the website. No real SMS gateway is
// connected on this static demo — these are the exact messages the system
// would send, shown so the audience can see the workflow.

export interface SmsAlert {
  id: string
  farmerName: string
  phone: string
  fieldName: string
  trigger: LangText
  message: LangText
  status: 'sent' | 'scheduled'
  sentAt: string
}

export const SMS_ALERTS: SmsAlert[] = [
  {
    id: 'sms-1',
    farmerName: 'Rafiqul Islam',
    phone: '+880 1XXX-XXXX55',
    fieldName: 'North paddy plot',
    trigger: { en: 'Season report ready', bn: 'মৌসুমের প্রতিবেদন তৈরি' },
    message: {
      en: 'AgriFusion BD: Your North paddy report is ready. Vegetation is below normal. Confidence is LOW — wait for the next clear satellite pass before deciding. Rabi suggestion: pulses/lentil. Check the app or call your officer.',
      bn: 'AgriFusion BD: আপনার উত্তর ধান প্লটের প্রতিবেদন তৈরি। গাছপালা স্বাভাবিকের চেয়ে কম। আস্থা কম — সিদ্ধান্তের আগে পরের পরিষ্কার ছবির অপেক্ষা করুন। রবির পরামর্শ: ডাল/মসুর। অ্যাপ দেখুন বা অফিসারকে ফোন করুন।',
    },
    status: 'sent',
    sentAt: '2026-10-20T08:05:00Z',
  },
  {
    id: 'sms-2',
    farmerName: 'Rafiqul Islam',
    phone: '+880 1XXX-XXXX55',
    fieldName: 'Pin estimate — east slope',
    trigger: { en: 'Drought warning', bn: 'খরা সতর্কতা' },
    message: {
      en: 'AgriFusion BD: WARNING — your east slope field is very dry (soil moisture 0.18). No irrigation source there. Do NOT sow before rain. Mulch now. Rain expected 17 Nov — sow chickpea after it.',
      bn: 'AgriFusion BD: সতর্কতা — আপনার পূর্ব ঢালের জমি খুব শুষ্ক (আর্দ্রতা ০.১৮)। সেখানে সেচের ব্যবস্থা নেই। বৃষ্টির আগে বপন করবেন না। এখনই খড় দিন। ২৭ অক্টোবর বৃষ্টি আশা করা হচ্ছে — তারপর ছোলা বুনুন।',
    },
    status: 'sent',
    sentAt: '2026-10-20T08:06:00Z',
  },
  {
    id: 'sms-3',
    farmerName: 'Rafiqul Islam',
    phone: '+880 1XXX-XXXX55',
    fieldName: 'River-bend plot',
    trigger: { en: 'Sowing window', bn: 'বপনের সময়' },
    message: {
      en: 'AgriFusion BD: Good news — your river-bend field is ready for Rabi mustard. Sow after 14 Nov. Watch drainage if rain is heavy on 17 Nov.',
      bn: 'AgriFusion BD: সুখবর — আপনার নদীর বাঁকের জমি রবি সরিষার জন্য তৈরি। ২৪ অক্টোবরের পর বুনুন। ২৭ অক্টোবর ভারী বৃষ্টি হলে পানি নিষ্কাশন দেখুন।',
    },
    status: 'scheduled',
    sentAt: '2026-10-24T06:00:00Z',
  },
  {
    id: 'sms-4',
    farmerName: 'Rafiqul Islam',
    phone: '+880 1XXX-XXXX55',
    fieldName: 'North paddy plot',
    trigger: { en: 'Pest alert', bn: 'পোকা সতর্কতা' },
    message: {
      en: 'AgriFusion BD: Rover found brown planthopper on your North paddy (medium). Check lower stems. If numbers rise in 5 days, contact your officer before spraying.',
      bn: 'AgriFusion BD: রোভার আপনার উত্তর ধান প্লটে বাদামি গাছফড়িং পেয়েছে (মাঝারি)। নিচের কাণ্ড দেখুন। ৫ দিনে সংখ্যা বাড়লে স্প্রে করার আগে অফিসারের সঙ্গে যোগাযোগ করুন।',
    },
    status: 'sent',
    sentAt: '2026-10-20T10:15:00Z',
  },
]

export function getSmsAlerts(): SmsAlert[] {
  return SMS_ALERTS
}
