export type SessionType = 'LT' | 'BT' | 'TH'

export type Weekday =
  | 'MONDAY'
  | 'TUESDAY'
  | 'WEDNESDAY'
  | 'THURSDAY'
  | 'FRIDAY'
  | 'SATURDAY'
  | 'SUNDAY'

export interface Session {
  type: SessionType
  // Chấp nhận cả số 2..8 (2 = Thứ 2, 8 = Chủ nhật) lẫn 'MONDAY'...'SUNDAY'
  // vì backend (constraints.py) đang dùng chữ, 
  day: number | Weekday
  periods: number[]
  room?: string
}
export interface ClassGroup {
  class_code: string
  lecturer?: string
  sessions: Session[]
}
export interface Course {
  course_code: string
  course_name: string
  credits?: number
  classes: ClassGroup[]
}

export interface UploadResponse {
  file_id: string
  headers: string[]
  mapping: Record<string, string | null>
  preview: string[][]
}

// ===== Ràng buộc (khớp backend/app/schemas/constraints.py) =====
export type TimeUnit = 'period' | 'ca'
export type PreferenceMode = 'prefer' | 'avoid'
export type ConstraintStrength = 'hard' | 'soft'
export type ParseStatus = 'ok' | 'needs_clarification'
export type IssueCode =
  | 'AMBIGUOUS'
  | 'UNSUPPORTED'
  | 'HARD_NOT_SUPPORTED'
  | 'UNIT_MISMATCH'
  | 'OUT_OF_RANGE'
  | 'UNKNOWN_COURSE'

export interface TimeRange {
  unit: TimeUnit
  start: number
  end: number
}
export interface TimeTarget {
  days: Weekday[]
  time_range: TimeRange | null
}
export interface WeightedDayOff {
  day: Weekday
  weight: number // 1..5
}
export interface HardTimeRule {
  mode: PreferenceMode
  target: TimeTarget
}
export interface WeightedTimeAvoidance {
  target: TimeTarget
  weight: number // 1..5
}
export interface CourseTimeRule {
  course_id: string
  mode: PreferenceMode
  strength: ConstraintStrength
  target: TimeTarget
  weight: number | null // soft: 1..5, hard: null
}
export interface ObjectiveWeights {
  compact_days: number // 0..5
  avoid_gaps: number // 0..5
}
export interface OptimizerConstraints {
  hard_days_off: Weekday[]
  hard_time_rules: HardTimeRule[]
  soft_days_off: WeightedDayOff[]
  avoid_times: WeightedTimeAvoidance[]
  per_course: CourseTimeRule[]
  weights: ObjectiveWeights
}
export interface PreferenceIssue {
  code: IssueCode
  message: string
  source_text: string
}
// POST /api/parse-preferences → PreferenceParseResult
export interface PreferenceParseResult {
  status: ParseStatus
  constraints: OptimizerConstraints
  issues: PreferenceIssue[]
}

// ===== Kết quả tối ưu (CHƯA có trong repo, đây là dạng frontend đang giả định) =====
export interface PlacedSession extends Session {
  course_code: string
  course_name: string
  class_code: string
}
export interface TimetableOption {
  score: number
  chosen: { course_code: string; class_code: string }[]
  sessions: PlacedSession[]
  explanation: string[]
}
export interface OptimizeStats {
  solve_ms: number
  status: string
  num_vars?: number
}
export interface OptimizeResponse {
  options: TimetableOption[]
  stats: OptimizeStats
}