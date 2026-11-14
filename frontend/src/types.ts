export type SessionType = 'LT' | 'BT' | 'TH'

export interface Session {
  type: SessionType
  day: number
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

export interface Constraints {
  hard: Record<string, unknown>[]
  soft: { type: string; weight: number; [k: string]: unknown }[]
  summary?: string
}

export interface TimetableOption {
  score: number
  chosen: { course_code: string; class_code: string }[]
  sessions: (Session & { course_code: string; course_name: string; class_code: string })[]
  explanation: string[]
}
export interface OptimizeResponse {
  options: TimetableOption[]
  stats: { solve_ms: number; status: string; num_vars?: number }
}