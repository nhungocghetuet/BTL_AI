import type {
  Course,
  IssueCode,
  OptimizerConstraints,
  TimeTarget,
  Weekday,
} from '../types'

export const EMPTY_CONSTRAINTS: OptimizerConstraints = {
  hard_days_off: [],
  hard_time_rules: [],
  soft_days_off: [],
  avoid_times: [],
  per_course: [],
  weights: { compact_days: 0, avoid_gaps: 0 },
}

export const WEEKDAY_LABEL: Record<Weekday, string> = {
  MONDAY: 'Thứ 2',
  TUESDAY: 'Thứ 3',
  WEDNESDAY: 'Thứ 4',
  THURSDAY: 'Thứ 5',
  FRIDAY: 'Thứ 6',
  SATURDAY: 'Thứ 7',
  SUNDAY: 'Chủ nhật',
}

const WEEKDAY_NUM: Record<Weekday, number> = {
  MONDAY: 2,
  TUESDAY: 3,
  WEDNESDAY: 4,
  THURSDAY: 5,
  FRIDAY: 6,
  SATURDAY: 7,
  SUNDAY: 8,
}

/** Đổi 'MONDAY' hoặc 2 về số 2..8. Không hợp lệ → NaN. */
export function dayToNumber(day: number | Weekday): number {
  if (typeof day === 'number') return day
  return WEEKDAY_NUM[day] ?? NaN
}

export function dayLabel(n: number): string {
  return n === 8 ? 'Chủ nhật' : `Thứ ${n}`
}

export const ISSUE_LABEL: Record<IssueCode, string> = {
  AMBIGUOUS: 'Chưa rõ nghĩa',
  UNSUPPORTED: 'Chưa hỗ trợ',
  HARD_NOT_SUPPORTED: 'Không hỗ trợ ràng buộc bắt buộc này',
  UNIT_MISMATCH: 'Sai đơn vị (tiết/ca)',
  OUT_OF_RANGE: 'Ngoài phạm vi',
  UNKNOWN_COURSE: 'Không tìm thấy môn học',
}

function describeTarget(t: TimeTarget): string {
  const parts: string[] = []
  if (t.days.length) parts.push(t.days.map((d) => WEEKDAY_LABEL[d] ?? d).join(', '))
  if (t.time_range) {
    const { unit, start, end } = t.time_range
    const noun = unit === 'ca' ? 'ca' : 'tiết'
    parts.push(start === end ? `${noun} ${start}` : `${noun} ${start}–${end}`)
  }
  return parts.join(' · ')
}

export interface Chip {
  id: string
  kind: 'hard' | 'soft'
  label: string
  weight?: number
  /** Trả về bản ràng buộc mới sau khi bỏ chip này. */
  remove: (c: OptimizerConstraints) => OptimizerConstraints
}

/** Biến JSON ràng buộc thành danh sách "chip" để người dùng đọc và xóa từng cái. */
export function buildChips(c: OptimizerConstraints, courses: Course[]): Chip[] {
  const chips: Chip[] = []
  const courseName = (id: string) =>
    courses.find((x) => x.course_code === id)?.course_name ?? id

  c.hard_days_off.forEach((d, i) =>
    chips.push({
      id: `hdo-${i}`,
      kind: 'hard',
      label: `Không học ${WEEKDAY_LABEL[d] ?? d}`,
      remove: (x) => ({ ...x, hard_days_off: x.hard_days_off.filter((_, j) => j !== i) }),
    }),
  )
  c.hard_time_rules.forEach((r, i) =>
    chips.push({
      id: `htr-${i}`,
      kind: 'hard',
      label: `${r.mode === 'avoid' ? 'Không học' : 'Bắt buộc học'} ${describeTarget(r.target)}`,
      remove: (x) => ({ ...x, hard_time_rules: x.hard_time_rules.filter((_, j) => j !== i) }),
    }),
  )
  c.soft_days_off.forEach((r, i) =>
    chips.push({
      id: `sdo-${i}`,
      kind: 'soft',
      label: `Ưu tiên nghỉ ${WEEKDAY_LABEL[r.day] ?? r.day}`,
      weight: r.weight,
      remove: (x) => ({ ...x, soft_days_off: x.soft_days_off.filter((_, j) => j !== i) }),
    }),
  )
  c.avoid_times.forEach((r, i) =>
    chips.push({
      id: `avt-${i}`,
      kind: 'soft',
      label: `Hạn chế học ${describeTarget(r.target)}`,
      weight: r.weight,
      remove: (x) => ({ ...x, avoid_times: x.avoid_times.filter((_, j) => j !== i) }),
    }),
  )
  c.per_course.forEach((r, i) =>
    chips.push({
      id: `pc-${i}`,
      kind: r.strength,
      label: `${courseName(r.course_id)}: ${r.mode === 'prefer' ? 'ưu tiên' : 'tránh'} ${describeTarget(r.target)}`,
      weight: r.weight ?? undefined,
      remove: (x) => ({ ...x, per_course: x.per_course.filter((_, j) => j !== i) }),
    }),
  )
  if (c.weights.compact_days > 0)
    chips.push({
      id: 'w-compact',
      kind: 'soft',
      label: 'Học dồn vào ít ngày',
      weight: c.weights.compact_days,
      remove: (x) => ({ ...x, weights: { ...x.weights, compact_days: 0 } }),
    })
  if (c.weights.avoid_gaps > 0)
    chips.push({
      id: 'w-gaps',
      kind: 'soft',
      label: 'Hạn chế tiết trống giữa buổi',
      weight: c.weights.avoid_gaps,
      remove: (x) => ({ ...x, weights: { ...x.weights, avoid_gaps: 0 } }),
    })
  return chips
}