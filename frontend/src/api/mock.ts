import type {
  Course,
  OptimizeResponse,
  OptimizerConstraints,
  PlacedSession,
  PreferenceIssue,
  PreferenceParseResult,
  TimetableOption,
  UploadResponse,
  Weekday,
} from '../types'
import { EMPTY_CONSTRAINTS, dayLabel, dayToNumber } from '../lib/constraints'
import { findConflicts } from '../lib/timetable'

// ---------- Upload (chưa làm xong api/upload.py) ----------
export const mockUpload: UploadResponse = {
  file_id: 'mock-123',
  headers: ['STT', 'Mã HP', 'Tên học phần', 'Mã LHP', 'Loại', 'Thứ', 'Tiết', 'Phòng', 'Giảng viên', 'Sĩ số'],
  mapping: {
    course_code: 'Mã HP',
    course_name: 'Tên học phần',
    class_code: 'Mã LHP',
    type: 'Loại',
    day: 'Thứ',
    periods: 'Tiết',
    room: 'Phòng',
    lecturer: null,
  },
  preview: [
    ['1', 'INT1001', 'Nhập môn lập trình', 'INT1001-01', 'LT', '2', '1,2,3', 'A101', 'Nguyễn Văn A', '60'],
    ['2', 'INT1001', 'Nhập môn lập trình', 'INT1001-01', 'TH', '4', '7,8', 'LAB2', 'Nguyễn Văn A', '30'],
    ['3', 'MAT1002', 'Giải tích 1', 'MAT1002-02', 'LT', '3', '9.1', 'B203', 'Trần Thị B', '80'],
  ],
}

// 5 môn x 2 lớp, thiết kế để cả 3 phương án mẫu đều không trùng lịch
export const mockCourses: Course[] = [
  {
    course_code: 'INT1001',
    course_name: 'Nhập môn lập trình',
    classes: [
      {
        class_code: 'INT1001-01',
        lecturer: 'Nguyễn Văn A',
        sessions: [
          { type: 'LT', day: 2, periods: [1, 2, 3], room: 'A101' },
          { type: 'TH', day: 4, periods: [7, 8], room: 'LAB2' },
        ],
      },
      {
        class_code: 'INT1001-02',
        lecturer: 'Lê Văn C',
        sessions: [
          { type: 'LT', day: 3, periods: [7, 8, 9], room: 'A102' },
          { type: 'TH', day: 5, periods: [1, 2], room: 'LAB1' },
        ],
      },
    ],
  },
  {
    course_code: 'MAT1002',
    course_name: 'Giải tích 1',
    classes: [
      {
        class_code: 'MAT1002-01',
        lecturer: 'Trần Thị B',
        sessions: [
          { type: 'LT', day: 3, periods: [1, 2, 3], room: 'B203' },
          { type: 'BT', day: 6, periods: [1, 2], room: 'B203' },
        ],
      },
      {
        class_code: 'MAT1002-02',
        lecturer: 'Phạm Văn D',
        sessions: [
          { type: 'LT', day: 2, periods: [7, 8, 9], room: 'B204' },
          { type: 'BT', day: 6, periods: [3, 4], room: 'B204' },
        ],
      },
    ],
  },
  {
    course_code: 'PHY1001',
    course_name: 'Vật lý đại cương',
    classes: [
      { class_code: 'PHY1001-01', sessions: [{ type: 'LT', day: 4, periods: [1, 2, 3], room: 'C301' }] },
      { class_code: 'PHY1001-02', sessions: [{ type: 'LT', day: 6, periods: [7, 8, 9], room: 'C302' }] },
    ],
  },
  {
    course_code: 'ENG1001',
    course_name: 'Tiếng Anh cơ bản',
    classes: [
      { class_code: 'ENG1001-01', sessions: [{ type: 'LT', day: 5, periods: [4, 5, 6], room: 'D101' }] },
      { class_code: 'ENG1001-02', sessions: [{ type: 'LT', day: 7, periods: [1, 2, 3], room: 'D102' }] },
    ],
  },
  {
    course_code: 'POL1001',
    course_name: 'Triết học Mác - Lênin',
    classes: [
      { class_code: 'POL1001-01', sessions: [{ type: 'LT', day: 2, periods: [4, 5, 6], room: 'E201' }] },
      { class_code: 'POL1001-02', sessions: [{ type: 'LT', day: 4, periods: [9, 10, 11], room: 'E202' }] },
    ],
  },
]

// ---------- Parse sở thích (mô phỏng đúng dạng JSON của backend) ----------
const DAY_BY_NUM: Record<string, Weekday> = {
  '2': 'MONDAY',
  '3': 'TUESDAY',
  '4': 'WEDNESDAY',
  '5': 'THURSDAY',
  '6': 'FRIDAY',
  '7': 'SATURDAY',
}

/** Bản mô phỏng đơn giản bằng từ khóa, chỉ để dựng và thử giao diện. */
export function mockParsePreferences(text: string): PreferenceParseResult {
  const t = text.toLowerCase()
  const c: OptimizerConstraints = structuredClone(EMPTY_CONSTRAINTS)

  for (const m of t.matchAll(/(ưu tiên nghỉ|không học|tránh|nghỉ)\s*(?:vào\s*)?(?:thứ\s*([2-7])|(chủ nhật))/g)) {
    const day: Weekday = m[3] ? 'SUNDAY' : DAY_BY_NUM[m[2]]
    if (m[1] === 'không học') c.hard_days_off.push(day)
    else c.soft_days_off.push({ day, weight: 3 })
  }
  const timeAvoid = (start: number, end: number) =>
    c.avoid_times.push({ target: { days: [], time_range: { unit: 'period', start, end } }, weight: 3 })
  if (/(tránh|không học|hạn chế)\s*(buổi\s*)?sáng/.test(t)) timeAvoid(1, 6)
  if (/(tránh|không học|hạn chế)\s*(buổi\s*)?chiều/.test(t)) timeAvoid(7, 12)
  for (const m of t.matchAll(/(tránh|không học|hạn chế)\s*tiết\s*(\d{1,2})/g)) timeAvoid(Number(m[2]), Number(m[2]))
  if (/dồn|ít ngày|tập trung/.test(t)) c.weights.compact_days = 3
  if (/trống|liền mạch|liên tục/.test(t)) c.weights.avoid_gaps = 3

  const understood =
    c.hard_days_off.length + c.soft_days_off.length + c.avoid_times.length + c.weights.compact_days + c.weights.avoid_gaps > 0
  const issues: PreferenceIssue[] = understood
    ? []
    : [
        {
          code: 'UNSUPPORTED',
          message:
            'Chưa hiểu yêu cầu này. (Bản mô phỏng chỉ nhận các câu như "không học thứ 7", "tránh buổi sáng", "học dồn vào ít ngày".)',
          source_text: text,
        },
      ]
  return { status: issues.length ? 'needs_clarification' : 'ok', constraints: c, issues }
}

// ---------- Optimize (chưa làm api/optimize.py) ----------
export function mockOptimize(selected: string[], courses: Course[]): OptimizeResponse {
  const chosen = courses.filter((c) => selected.includes(c.course_code) && c.classes.length > 0)
  const seen = new Set<string>()
  const options: TimetableOption[] = []
  if (chosen.length === 0) return { options, stats: { solve_ms: 0, status: 'MOCK', num_vars: 0 } }

  for (let k = 0; k < 3; k++) {
    const picks = chosen.map((course, i) => ({
      course,
      cls: course.classes[(k === 2 ? i : k) % course.classes.length],
    }))
    const key = picks.map((p) => p.cls.class_code).join('|')
    if (seen.has(key)) continue
    seen.add(key)

    const sessions: PlacedSession[] = picks.flatMap(({ course, cls }) =>
      cls.sessions.map((s) => ({
        ...s,
        course_code: course.course_code,
        course_name: course.course_name,
        class_code: cls.class_code,
      })),
    )
    const days = [...new Set(sessions.map((s) => dayToNumber(s.day)))].sort((a, b) => a - b)
    const allPeriods = sessions.flatMap((s) => s.periods)
    const conflicts = findConflicts(sessions).length
    options.push({
      score: 100 - options.length * 6,
      chosen: picks.map((p) => ({ course_code: p.course.course_code, class_code: p.cls.class_code })),
      sessions,
      explanation: [
        conflicts === 0 ? 'Không có buổi nào trùng lịch.' : `Có ${conflicts} cặp buổi trùng lịch.`,
        `Học trong ${days.length} ngày: ${days.map(dayLabel).join(', ')}.`,
        `Tiết sớm nhất là ${Math.min(...allPeriods)}, muộn nhất là ${Math.max(...allPeriods)}.`,
        '(Dữ liệu mô phỏng, chưa phải kết quả của bộ tối ưu CP-SAT.)',
      ],
    })
  }
  return { options, stats: { solve_ms: 120, status: 'MOCK', num_vars: chosen.length * 2 } }
}