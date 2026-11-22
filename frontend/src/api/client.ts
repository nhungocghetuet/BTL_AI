import axios from 'axios'
import type {
  Course,
  OptimizeResponse,
  OptimizerConstraints,
  PreferenceParseResult,
  UploadResponse,
} from '../types'
import { mockCourses, mockOptimize, mockParsePreferences, mockUpload } from './mock'

// Mỗi nhóm API có cờ mock riêng vì backend xong từng phần một:
//   VITE_USE_MOCK        = mặc định cho tất cả
//   VITE_MOCK_UPLOAD / VITE_MOCK_PREFERENCES / VITE_MOCK_OPTIMIZE = ghi đè từng nhóm
const GLOBAL_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const flag = (name: string): boolean => {
  const v = import.meta.env[name]
  return v === undefined || v === '' ? GLOBAL_MOCK : v === 'true'
}
const MOCK_UPLOAD = flag('VITE_MOCK_UPLOAD')
const MOCK_PREFERENCES = flag('VITE_MOCK_PREFERENCES')
const MOCK_OPTIMIZE = flag('VITE_MOCK_OPTIMIZE')

// Backend gắn router với prefix settings.API_PREFIX = "/api" (backend/app/config.py)
const PREFIX: string = import.meta.env.VITE_API_PREFIX ?? '/api'

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000' })
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export async function uploadFile(file: File): Promise<UploadResponse> {
  if (MOCK_UPLOAD) {
    await sleep(800)
    return mockUpload
  }
  const fd = new FormData()
  fd.append('file', file)
  return (await api.post(`${PREFIX}/upload`, fd)).data
}

export async function confirmMapping(
  file_id: string,
  mapping: Record<string, string | null>,
): Promise<{ courses: Course[] }> {
  if (MOCK_UPLOAD) {
    await sleep(600)
    return { courses: mockCourses }
  }
  return (await api.post(`${PREFIX}/upload/confirm`, { file_id, mapping })).data
}

/**
 * Số buổi học mỗi tuần của môn. Backend chỉ hỗ trợ yêu cầu theo từng môn
 * khi môn có đúng 1 buổi/tuần, và báo AMBIGUOUS nếu không biết số buổi.
 * Nếu các lớp của môn có số buổi khác nhau thì coi là không xác định.
 */
function weeklyMeetingCount(c: Course): number | undefined {
  const counts = [...new Set(c.classes.map((k) => k.sessions.length))]
  return counts.length === 1 && counts[0] >= 1 ? counts[0] : undefined
}

/**
 * Khớp class SelectedCourse trong backend/app/services/ai/preference_parser.py
 * (extra="forbid" nên không được gửi thêm trường khác).
 */
function toSelectedCourse(c: Course) {
  return {
    course_id: c.course_code,
    course_name: c.course_name.trim() || c.course_code,
    weekly_meeting_count: weeklyMeetingCount(c), // undefined sẽ bị bỏ khỏi JSON
  }
}

export async function parsePreferences(text: string, courses: Course[]): Promise<PreferenceParseResult> {
  if (MOCK_PREFERENCES) {
    await sleep(500)
    return mockParsePreferences(text)
  }
  return (await api.post(`${PREFIX}/parse-preferences`, { text, selected_courses: courses.map(toSelectedCourse) }))
    .data
}

export async function optimize(
  course_ids: string[],
  constraints: OptimizerConstraints,
  courses: Course[], // chỉ dùng cho bản mock
): Promise<OptimizeResponse> {
  if (MOCK_OPTIMIZE) {
    await sleep(800)
    return mockOptimize(course_ids, courses)
  }
  return (await api.post(`${PREFIX}/optimize`, { course_ids, constraints })).data
}