// AgriFusion BD domain types.
// These mirror the logical data model in the project report (section 8).
// The API client in `api.ts` returns these shapes; the Django backend is
// expected to conform to the same contracts via drf-spectacular / OpenAPI.

export type Role = 'farmer' | 'officer' | 'researcher' | 'rover_operator' | 'admin'

export type Language = 'en' | 'bn'

export interface User {
  id: string
  name: string
  roles: Role[]
  organization?: string
  locale: Language
}

export type FieldStatus = 'active' | 'archived'

export interface Field {
  id: string
  farmId: string
  name: string
  /** GeoJSON Polygon, SRID 4326 */
  geometry: { type: 'Polygon'; coordinates: number[][][] }
  areaHa: number
  soilType?: string
  irrigation: 'rainfed' | 'canal' | 'pump' | 'tubewell'
  priorities: string[]
  status: FieldStatus
  updatedAt: string
  isPinEstimate: boolean
}

export type CropFamily = 'grasses' | 'legumes' | 'brassicas' | 'pulses' | 'root' | 'tuber' | 'vegetable' | 'fiber'

export interface Crop {
  id: string
  name: string
  nameBn: string
  family: CropFamily
  seasonMonths: [number, number]
  waterDemandMm: [number, number]
  priceRangeBdtPerKg: [number, number]
  costPerHaBdt: [number, number]
  yieldRangeT: [number, number]
  /** 0-1, 1 = very heat tolerant */
  heatTolerance: number
  /** 0-1, 1 = very drought tolerant */
  droughtTolerance: number
}

export interface CropHistory {
  fieldId: string
  year: number
  cropId: string
  yieldT?: number
  notes?: string
}

export interface SoilTest {
  id: string
  fieldId: string
  takenAt: string
  ph: number
  organicMatterPct: number
  ecDsM: number
  nitrogenPpm: number
  phosphorusPpm: number
  potassiumPpm: number
  lab?: string
}

// --- Environmental ---

export type DataAssetKind = 'power_dailies' | 'hls_vi' | 'rover' | 'local' | 'forecast'

export interface DataAsset {
  id: string
  kind: DataAssetKind
  provider: string
  product: string
  version: string
  /** ISO date range the asset covers */
  validFrom: string
  validTo: string
  spatialRes: string
  coveragePct: number
  stale?: boolean
  retrievedAt: string
}

export interface FieldIndicator {
  fieldId: string
  date: string
  kind: DataAssetKind
  /** e.g. "rainfall_mm", "ndvi", "soil_moisture_pct", "temp_mean_c" */
  metric: string
  value: number
  unit: string
  coveragePct: number
  quality: 'ok' | 'partial' | 'missing'
  assetId: string
}

// --- Analysis ---

export type AnalysisStatus =
  | 'queued'
  | 'running'
  | 'complete'
  | 'partial'
  | 'failed'
  | 'cancelled'

export interface AnalysisRequest {
  fieldId: string
  seasonStart: string
  seasonEnd: string
  /** Farmer-selected weights 0-1; sum need not be 1 */
  weights: {
    waterEfficiency: number
    heatResilience: number
    soilCover: number
    rotationDiversity: number
    economics: number
  }
  excludeCropIds?: string[]
}

export interface MetricValue {
  key: keyof AnalysisRequest['weights']
  label: string
  /** 0-1 normalized within declared bounds */
  score: number
  rawValue: string
  qualification: string
  warning?: string
}

export interface RotationPlan {
  id: string
  kind: 'baseline' | 'alternative'
  cropIds: string[]
  /** month-by-month timeline, 12 entries */
  timeline: { month: number; cropId?: string }[]
  metrics: MetricValue[]
  weightedScore: number
  feasibility: 'feasible' | 'constrained' | 'infeasible'
  reasons: string[]
}

export interface AnalysisRun {
  id: string
  fieldId: string
  status: AnalysisStatus
  progressPct: number
  submittedAt: string
  completedAt?: string
  ruleVersion: string
  idempotencyKey: string
  request: AnalysisRequest
  plans?: RotationPlan[]
  warnings?: string[]
  evidence?: {
    assets: DataAsset[]
    indicators: FieldIndicator[]
    assumptions: string[]
    missingData: string[]
  }
  error?: string
}

// --- Cases ---

export type CaseStatus = 'open' | 'in_review' | 'resolved' | 'rejected'

export interface CaseMessage {
  id: string
  authorRole: Role
  body: string
  at: string
}

export interface AssistanceCase {
  id: string
  fieldId: string
  farmerId: string
  subject: string
  status: CaseStatus
  assignedOfficerId?: string
  createdAt: string
  updatedAt: string
  messages: CaseMessage[]
}

// --- Rover ---

export interface RoverDevice {
  id: string
  name: string
  model: string
  status: 'idle' | 'on_mission' | 'service_due' | 'offline'
  batteryPct: number
  lastSeenAt: string
  grantExpiresAt?: string
  fieldIds: string[]
}

export interface RoverObservation {
  id: string
  deviceId: string
  messageId: string
  fieldId: string
  measuredAt: string
  uploadedAt: string
  coordinates: [number, number]
  gpsAccuracyM: number
  depthCm: number
  sensor: 'moisture' | 'temperature' | 'ec'
  value: number
  unit: string
  calibrationId: string
  quality: 'ok' | 'flagged' | 'rejected'
}

// --- Research ---

export interface ResearchExportJob {
  id: string
  createdAt: string
  scope: string
  format: 'csv' | 'geojson'
  status: 'queued' | 'running' | 'complete' | 'failed'
  rowCount?: number
  provenance?: {
    ruleVersion: string
    dataSnapshots: string[]
    generatedAt: string
  }
}

export interface ResearchLocation {
  id: string
  name: string
  coordinates: [number, number]
  period: string
  coveragePct: number
  series: { date: string; ndvi: number; rainfallMm: number }[]
}
