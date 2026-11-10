import type {
  AnalysisRun,
  AssistanceCase,
  Crop,
  CropHistory,
  Field,
  FieldIndicator,
  ResearchExportJob,
  ResearchLocation,
  RoverDevice,
  RoverObservation,
  RotationPlan,
  SoilTest,
  User,
} from './types'

// Deterministic mock data for the pilot demo. In production this is served by
// the Django REST API; the shapes are the same (see lib/types.ts).
// Coordinates are in the pilot area of northern Bangladesh (Rajshahi/Dinajpur).

const FARMER: User = {
  id: 'u-farmer-1',
  name: 'Rafiqul Islam',
  roles: ['farmer'],
  locale: 'bn',
}

export const USERS: Record<string, User> = {
  farmer: FARMER,
  officer: {
    id: 'u-officer-1',
    name: 'Nasrin Akter',
    roles: ['officer'],
    organization: 'Dinajpur DAE',
    locale: 'bn',
  },
  researcher: {
    id: 'u-researcher-1',
    name: 'Dr. Tanvir Hasan',
    roles: ['researcher'],
    organization: 'BSRM',
    locale: 'en',
  },
  rover_operator: {
    id: 'u-rover-1',
    name: 'Kamal Uddin',
    roles: ['rover_operator'],
    locale: 'bn',
  },
}

export const CROPS: Crop[] = [
  {
    id: 'c-rice-boro',
    name: 'Boro Rice',
    nameBn: 'বোরো ধান',
    family: 'grasses',
    seasonMonths: [12, 5],
    waterDemandMm: [420, 560],
    priceRangeBdtPerKg: [14, 18],
    costPerHaBdt: [65000, 90000],
    yieldRangeT: [3.2, 4.8],
    heatTolerance: 0.55,
    droughtTolerance: 0.2,
  },
  {
    id: 'c-wheat',
    name: 'Wheat',
    nameBn: 'গম',
    family: 'grasses',
    seasonMonths: [10, 3],
    waterDemandMm: [280, 380],
    priceRangeBdtPerKg: [13, 17],
    costPerHaBdt: [38000, 55000],
    yieldRangeT: [2.4, 3.6],
    heatTolerance: 0.4,
    droughtTolerance: 0.55,
  },
  {
    id: 'c-mustard',
    name: 'Mustard',
    nameBn: 'সরিষা',
    family: 'brassicas',
    seasonMonths: [9, 1],
    waterDemandMm: [140, 220],
    priceRangeBdtPerKg: [95, 130],
    costPerHaBdt: [22000, 34000],
    yieldRangeT: [0.9, 1.4],
    heatTolerance: 0.35,
    droughtTolerance: 0.6,
  },
  {
    id: 'c-maize',
    name: 'Maize',
    nameBn: 'ভুট্টা',
    family: 'grasses',
    seasonMonths: [2, 8],
    waterDemandMm: [320, 450],
    priceRangeBdtPerKg: [22, 32],
    costPerHaBdt: [30000, 48000],
    yieldRangeT: [3.0, 4.5],
    heatTolerance: 0.6,
    droughtTolerance: 0.5,
  },
  {
    id: 'c-mungbean',
    name: 'Mungbean',
    nameBn: 'মসুর',
    family: 'legumes',
    seasonMonths: [7, 10],
    waterDemandMm: [180, 260],
    priceRangeBdtPerKg: [110, 150],
    costPerHaBdt: [18000, 28000],
    yieldRangeT: [0.7, 1.1],
    heatTolerance: 0.65,
    droughtTolerance: 0.5,
  },
  {
    id: 'c-potato',
    name: 'Potato',
    nameBn: 'আলু',
    family: 'tuber',
    seasonMonths: [10, 2],
    waterDemandMm: [260, 360],
    priceRangeBdtPerKg: [45, 80],
    costPerHaBdt: [55000, 85000],
    yieldRangeT: [18, 28],
    heatTolerance: 0.3,
    droughtTolerance: 0.4,
  },
]

function polygon(cx: number, cy: number, r: number, sides = 6): number[][][] {
  const coords: number[][] = []
  for (let i = 0; i <= sides; i++) {
    const a = (i / sides) * Math.PI * 2
    const jitter = 0.82 + 0.18 * Math.sin(i * 2.3 + cx * 100)
    coords.push([cx + r * Math.cos(a) * jitter, cy + r * Math.sin(a) * jitter * 0.8])
  }
  return [coords]
}

export const FIELDS: Field[] = [
  {
    id: 'f-1',
    farmId: 'farm-1',
    name: 'North paddy plot',
    geometry: { type: 'Polygon', coordinates: polygon(88.604, 25.342, 0.001015) },
    areaHa: 2.4,
    soilType: 'Alluvial, medium-heavy clay',
    irrigation: 'canal',
    priorities: ['water_efficiency', 'soil_cover'],
    status: 'active',
    updatedAt: '2026-10-28T06:12:00Z',
    isPinEstimate: false,
    currentCycleCrops: ['T. Aman'],
    recentCycleCrops: ['Boro'],
  },
  {
    id: 'f-2',
    farmId: 'farm-1',
    name: 'River-bend plot',
    geometry: { type: 'Polygon', coordinates: polygon(88.622, 25.331, 0.000687) },
    areaHa: 1.1,
    soilType: 'Alluvial, sandy-loam',
    irrigation: 'pump',
    priorities: ['economics'],
    status: 'active',
    updatedAt: '2026-10-12T09:40:00Z',
    isPinEstimate: false,
    currentCycleCrops: ['T. Aman'],
    recentCycleCrops: ['Wheat'],
  },
  {
    id: 'f-3',
    farmId: 'farm-1',
    name: 'Pin estimate — east slope',
    geometry: { type: 'Polygon', coordinates: polygon(88.641, 25.35, 0.000359) },
    areaHa: 0.3,
    irrigation: 'rainfed',
    priorities: ['rotation_diversity'],
    status: 'active',
    updatedAt: '2026-09-30T11:05:00Z',
    isPinEstimate: true,
    currentCycleCrops: ['Lentil'],
    recentCycleCrops: ['Fallow'],
  },
]

export const CROP_HISTORY: CropHistory[] = [
  { fieldId: 'f-1', year: 2024, cropId: 'c-rice-boro', yieldT: 4.1 },
  { fieldId: 'f-1', year: 2025, cropId: 'c-rice-boro', yieldT: 3.8 },
  { fieldId: 'f-1', year: 2025, cropId: 'c-mustard', yieldT: 1.0 },
  { fieldId: 'f-2', year: 2024, cropId: 'c-maize', yieldT: 3.9 },
  { fieldId: 'f-2', year: 2025, cropId: 'c-mungbean', yieldT: 0.95 },
]

export const SOIL_TESTS: SoilTest[] = [
  {
    id: 'st-1',
    fieldId: 'f-1',
    takenAt: '2026-08-14',
    ph: 6.4,
    organicMatterPct: 1.8,
    ecDsM: 0.4,
    nitrogenPpm: 210,
    phosphorusPpm: 12,
    potassiumPpm: 145,
    lab: 'DAE Dinajpur',
  },
]

// --- Environmental series (POWER dailies + HLS VI, demo subset) ---

function series(fieldId: string, metric: string, unit: string, kind: 'power_dailies' | 'hls_vi', n = 90, base = 50, amp = 20): FieldIndicator[] {
  const out: FieldIndicator[] = []
  const end = new Date('2026-10-28')
  for (let i = 0; i < n; i++) {
    const d = new Date(end)
    d.setDate(d.getDate() - (n - 1 - i))
    const wave = Math.sin(i / 9 + fieldId.length) * amp
    const value = Math.round((base + wave + (i % 7) * 0.6) * 100) / 100
    const quality = i % 19 === 0 ? 'partial' : 'ok'
    out.push({
      fieldId,
      date: d.toISOString().slice(0, 10),
      kind,
      metric,
      value,
      unit,
      coveragePct: quality === 'partial' ? 62 + (i % 20) : 94 + (i % 6),
      quality,
      assetId: `a-${kind}`,
    })
  }
  return out
}

export const INDICATORS: FieldIndicator[] = [
  ...series('f-1', 'rainfall_mm', 'mm', 'power_dailies', 90, 18, 26),
  ...series('f-1', 'temp_mean_c', '°C', 'power_dailies', 90, 27, 6),
  ...series('f-1', 'ndvi', 'index', 'hls_vi', 60, 0.52, 0.16),
  ...series('f-2', 'rainfall_mm', 'mm', 'power_dailies', 90, 15, 22),
  ...series('f-2', 'ndvi', 'index', 'hls_vi', 60, 0.46, 0.14),
]

export const ASSETS = [
  {
    id: 'a-power',
    kind: 'power_dailies' as const,
    provider: 'NASA POWER',
    product: 'daily',
    version: 'v7',
    validFrom: '2026-07-30',
    validTo: '2026-10-28',
    spatialRes: '0.5°',
    coveragePct: 96,
    retrievedAt: '2026-10-29T02:11:00Z',
  },
  {
    id: 'a-hls',
    kind: 'hls_vi' as const,
    provider: 'Landsat / NASA HLS',
    product: 'HLSL30.VI',
    version: '2.0',
    validFrom: '2026-08-20',
    validTo: '2026-10-26',
    spatialRes: '30 m',
    coveragePct: 78,
    retrievedAt: '2026-10-29T03:40:00Z',
  },
]

// --- Analysis runs ---

function makePlans(_fieldId: string): RotationPlan[] {
  const baseline: RotationPlan = {
    id: 'p-base',
    kind: 'baseline' as const,
    cropIds: ['c-rice-boro', 'c-mustard'],
    timeline: [
      { month: 1, cropId: 'c-rice-boro' },
      { month: 2, cropId: 'c-rice-boro' },
      { month: 3, cropId: 'c-rice-boro' },
      { month: 4, cropId: 'c-rice-boro' },
      { month: 5, cropId: 'c-rice-boro' },
      { month: 6, cropId: undefined },
      { month: 7, cropId: undefined },
      { month: 8, cropId: undefined },
      { month: 9, cropId: 'c-mustard' },
      { month: 10, cropId: 'c-mustard' },
      { month: 11, cropId: 'c-mustard' },
      { month: 12, cropId: undefined },
    ],
    metrics: [
      { key: 'waterEfficiency', label: 'Water demand', score: 0.42, rawValue: '≈ 640 mm season', qualification: 'Reference ET × crop coefficients; canal irrigation 70% efficient', warning: 'Boro stage overlaps low-canal months' },
      { key: 'heatResilience', label: 'Heat & dry exposure', score: 0.48, rawValue: '2 windows > 33°C at flowering', qualification: 'Historical scenario alignment; not a forecast' },
      { key: 'soilCover', label: 'Soil cover', score: 0.61, rawValue: '≈ 71% covered months', qualification: 'Calendar + HLS VI; inferred where clouded' },
      { key: 'rotationDiversity', label: 'Rotation diversity', score: 0.35, rawValue: '2 families, rice repeated', qualification: 'Planning indicator only' },
      { key: 'economics', label: 'Economics', score: 0.58, rawValue: 'Bdt 52k–88k net range', qualification: 'Local price/cost ranges; no guaranteed profit' },
    ],
    weightedScore: 0.48,
    feasibility: 'feasible',
    reasons: ['Matches 2-year history', 'Canal water available Dec–May'],
  }
  const alt1: RotationPlan = {
    id: 'p-alt1',
    kind: 'alternative' as const,
    cropIds: ['c-maize', 'c-mungbean'],
    timeline: [
      { month: 1, cropId: undefined },
      { month: 2, cropId: 'c-maize' },
      { month: 3, cropId: 'c-maize' },
      { month: 4, cropId: 'c-maize' },
      { month: 5, cropId: 'c-maize' },
      { month: 6, cropId: 'c-maize' },
      { month: 7, cropId: 'c-mungbean' },
      { month: 8, cropId: 'c-mungbean' },
      { month: 9, cropId: 'c-mungbean' },
      { month: 10, cropId: undefined },
      { month: 11, cropId: undefined },
      { month: 12, cropId: undefined },
    ],
    metrics: [
      { key: 'waterEfficiency', label: 'Water demand', score: 0.66, rawValue: '≈ 520 mm season', qualification: 'Maize needs less standing water than boro', warning: 'Irrigation window Jun–Jul tight' },
      { key: 'heatResilience', label: 'Heat & dry exposure', score: 0.62, rawValue: '1 sensitive window (tasseling)', qualification: 'Historical scenario alignment' },
      { key: 'soilCover', label: 'Soil cover', score: 0.7, rawValue: '≈ 80% covered months', qualification: 'Denser canopy months Mar–Jun' },
      { key: 'rotationDiversity', label: 'Rotation diversity', score: 0.82, rawValue: '2 families + legume fixer', qualification: 'Mungbean breaks grass-family repetition' },
      { key: 'economics', label: 'Economics', score: 0.64, rawValue: 'Bdt 44k–79k net range', qualification: 'Higher input variance; mungbean market stable' },
    ],
    weightedScore: 0.68,
    feasibility: 'feasible',
    reasons: ['Legume inclusion improves rotation', 'Maize market premium in pilot area'],
  }
  const alt2: RotationPlan = {
    id: 'p-alt2',
    kind: 'alternative' as const,
    cropIds: ['c-wheat', 'c-mustard'],
    timeline: [
      { month: 1, cropId: 'c-wheat' },
      { month: 2, cropId: 'c-wheat' },
      { month: 3, cropId: 'c-wheat' },
      { month: 4, cropId: undefined },
      { month: 5, cropId: undefined },
      { month: 6, cropId: undefined },
      { month: 7, cropId: undefined },
      { month: 8, cropId: undefined },
      { month: 9, cropId: 'c-mustard' },
      { month: 10, cropId: 'c-mustard' },
      { month: 11, cropId: 'c-mustard' },
      { month: 12, cropId: 'c-mustard' },
    ],
    metrics: [
      { key: 'waterEfficiency', label: 'Water demand', score: 0.74, rawValue: '≈ 420 mm season', qualification: 'Lowest of the three; rainfed share higher' },
      { key: 'heatResilience', label: 'Heat & dry exposure', score: 0.55, rawValue: 'Wheat heading sensitive to heat', qualification: 'Historical scenario alignment' },
      { key: 'soilCover', label: 'Soil cover', score: 0.58, rawValue: '≈ 68% covered months', qualification: 'Bare fallow Jul–Aug noted' },
      { key: 'rotationDiversity', label: 'Rotation diversity', score: 0.71, rawValue: '2 families, no grass repetition', qualification: 'Breaks rice-rice pattern' },
      { key: 'economics', label: 'Economics', score: 0.51, rawValue: 'Bdt 38k–62k net range', qualification: 'Lower revenue ceiling; lower risk' },
    ],
    weightedScore: 0.61,
    feasibility: 'constrained',
    reasons: ['Wheat requires cold window Oct–Mar', 'Mustard seed supply limited locally'],
  }
  return [baseline, alt1, alt2]
}

export const ANALYSES: AnalysisRun[] = [
  {
    id: 'an-1',
    fieldId: 'f-1',
    status: 'complete',
    progressPct: 100,
    submittedAt: '2026-10-28T14:02:00Z',
    completedAt: '2026-10-28T14:04:12Z',
    ruleVersion: 'v2026.10.2',
    idempotencyKey: 'ik-f1-2026',
    request: {
      fieldId: 'f-1',
      seasonStart: '2026-12-01',
      seasonEnd: '2027-11-30',
      weights: { waterEfficiency: 0.4, heatResilience: 0.25, soilCover: 0.1, rotationDiversity: 0.1, economics: 0.15 },
    },
    plans: makePlans('f-1'),
    warnings: ['HLS coverage 78% — bare-field inference limited for 2 boundary months'],
    evidence: {
      assets: ASSETS,
      indicators: INDICATORS.filter((i) => i.fieldId === 'f-1').slice(0, 30),
      assumptions: [
        'Canal irrigation efficiency 70% (pilot default)',
        'Crop coefficients from FAO-56 local calibration',
        'Yield ranges from BSRM 2024–25 district averages',
      ],
      missingData: ['Jun–Jul NDVI (cloud cover)', 'EC at 30 cm depth'],
    },
  },
  {
    id: 'an-2',
    fieldId: 'f-2',
    status: 'complete',
    progressPct: 100,
    submittedAt: '2026-10-15T08:20:00Z',
    completedAt: '2026-10-15T08:22:40Z',
    ruleVersion: 'v2026.10.2',
    idempotencyKey: 'ik-f2-2026',
    request: {
      fieldId: 'f-2',
      seasonStart: '2026-12-01',
      seasonEnd: '2027-11-30',
      weights: { waterEfficiency: 0.2, heatResilience: 0.2, soilCover: 0.1, rotationDiversity: 0.1, economics: 0.4 },
    },
    plans: makePlans('f-2'),
    evidence: {
      assets: ASSETS,
      indicators: INDICATORS.filter((i) => i.fieldId === 'f-2').slice(0, 20),
      assumptions: ['Pump irrigation efficiency 55%', 'Maize variety: BARI-Mzt-22 (assumed)'],
      missingData: ['Rover moisture calibration pending'],
    },
  },
  {
    id: 'an-3',
    fieldId: 'f-1',
    status: 'running',
    progressPct: 58,
    submittedAt: '2026-10-29T06:41:00Z',
    ruleVersion: 'v2026.10.2',
    idempotencyKey: 'ik-f1-replay-2025',
    request: {
      fieldId: 'f-1',
      seasonStart: '2025-12-01',
      seasonEnd: '2026-11-30',
      weights: { waterEfficiency: 0.4, heatResilience: 0.25, soilCover: 0.1, rotationDiversity: 0.1, economics: 0.15 },
    },
  },
]

export const CASES: AssistanceCase[] = [
  {
    id: 'case-1',
    fieldId: 'f-1',
    farmerId: 'u-farmer-1',
    subject: 'Rover inspection — soil moisture check after dry spell',
    status: 'in_review',
    assignedOfficerId: 'u-officer-1',
    createdAt: '2026-10-25T10:00:00Z',
    updatedAt: '2026-10-27T15:30:00Z',
    messages: [
      { id: 'm1', authorRole: 'farmer', body: 'Field f-1 has been dry for 12 days. Can we get a rover visit before boro sowing?', at: '2026-10-25T10:00:00Z' },
      { id: 'm2', authorRole: 'officer', body: 'Acknowledged. Scheduling rover window 27 Oct. Please keep the north boundary accessible.', at: '2026-10-25T14:22:00Z' },
      { id: 'm3', authorRole: 'farmer', body: 'Confirmed. Access from the east road.', at: '2026-10-26T08:11:00Z' },
    ],
  },
  {
    id: 'case-2',
    fieldId: 'f-2',
    farmerId: 'u-farmer-1',
    subject: 'Maize seed subsidy eligibility',
    status: 'resolved',
    assignedOfficerId: 'u-officer-1',
    createdAt: '2026-09-30T09:00:00Z',
    updatedAt: '2026-10-08T11:45:00Z',
    messages: [
      { id: 'm4', authorRole: 'farmer', body: 'Is f-2 eligible for the maize seed support this season?', at: '2026-09-30T09:00:00Z' },
      { id: 'm5', authorRole: 'officer', body: 'Yes, documented. Certificate sent by SMS. Verify with your local DAE office.', at: '2026-10-08T11:45:00Z' },
    ],
  },
]

export const DEVICES: RoverDevice[] = [
  {
    id: 'rv-1',
    name: 'FS-Rover 01',
    model: 'AgraBot X2',
    status: 'idle',
    batteryPct: 82,
    lastSeenAt: '2026-10-29T05:12:00Z',
    grantExpiresAt: '2027-03-01',
    fieldIds: ['f-1', 'f-2'],
  },
  {
    id: 'rv-2',
    name: 'FS-Rover 02',
    model: 'AgraBot X2',
    status: 'on_mission',
    batteryPct: 41,
    lastSeenAt: '2026-10-29T06:02:00Z',
    grantExpiresAt: '2026-12-15',
    fieldIds: ['f-3'],
  },
]

export const OBSERVATIONS: RoverObservation[] = [
  { id: 'o-1', deviceId: 'rv-1', messageId: 'msg-0001', fieldId: 'f-1', measuredAt: '2026-10-27T04:30:00Z', uploadedAt: '2026-10-27T04:31:12Z', coordinates: [88.6041, 25.3422], gpsAccuracyM: 0.8, depthCm: 10, sensor: 'moisture', value: 24.6, unit: '%VWC', calibrationId: 'cal-2026-09', quality: 'ok' },
  { id: 'o-2', deviceId: 'rv-1', messageId: 'msg-0002', fieldId: 'f-1', measuredAt: '2026-10-27T04:31:00Z', uploadedAt: '2026-10-27T04:31:12Z', coordinates: [88.6041, 25.3422], gpsAccuracyM: 0.8, depthCm: 30, sensor: 'moisture', value: 27.1, unit: '%VWC', calibrationId: 'cal-2026-09', quality: 'ok' },
  { id: 'o-3', deviceId: 'rv-1', messageId: 'msg-0003', fieldId: 'f-1', measuredAt: '2026-10-27T04:32:00Z', uploadedAt: '2026-10-27T04:31:12Z', coordinates: [88.6041, 25.3422], gpsAccuracyM: 0.9, depthCm: 10, sensor: 'temperature', value: 29.4, unit: '°C', calibrationId: 'cal-2026-09', quality: 'ok' },
  { id: 'o-4', deviceId: 'rv-2', messageId: 'msg-0041', fieldId: 'f-3', measuredAt: '2026-10-29T05:44:00Z', uploadedAt: '2026-10-29T06:02:00Z', coordinates: [88.641, 25.35], gpsAccuracyM: 1.6, depthCm: 10, sensor: 'ec', value: 0.62, unit: 'dS/m', calibrationId: 'cal-2026-08', quality: 'flagged' },
]

export const RESEARCH_LOCATIONS: ResearchLocation[] = [
  {
    id: 'loc-1',
    name: 'Dinajpur station',
    coordinates: [88.635, 25.282],
    period: '2024-2026',
    coveragePct: 91,
    series: Array.from({ length: 24 }, (_, i) => {
      const d = new Date(2024, i, 15)
      return {
        date: d.toISOString().slice(0, 7),
        ndvi: 0.38 + 0.22 * Math.sin(i / 2),
        rainfallMm: 30 + 90 * Math.max(0, Math.sin((i - 3) / 3)),
      }
    }),
  },
  {
    id: 'loc-2',
    name: 'Rajshahi grid cell',
    coordinates: [88.6, 24.37],
    period: '2024-2026',
    coveragePct: 84,
    series: Array.from({ length: 24 }, (_, i) => {
      const d = new Date(2024, i, 15)
      return {
        date: d.toISOString().slice(0, 7),
        ndvi: 0.34 + 0.18 * Math.sin(i / 2 + 0.4),
        rainfallMm: 25 + 80 * Math.max(0, Math.sin((i - 4) / 3)),
      }
    }),
  },
]

export const EXPORT_JOBS: ResearchExportJob[] = [
  {
    id: 'exp-1',
    createdAt: '2026-10-20T11:00:00Z',
    scope: 'f-1 · 2026 season · POWER + HLS',
    format: 'csv',
    status: 'complete',
    rowCount: 96,
    provenance: { ruleVersion: 'v2026.10.2', dataSnapshots: ['a-power', 'a-hls'], generatedAt: '2026-10-20T11:02:00Z' },
  },
]
