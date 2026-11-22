import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  Course,
  OptimizeResponse,
  OptimizeStats,
  OptimizerConstraints,
  ParseStatus,
  PreferenceIssue,
  PreferenceParseResult,
  TimetableOption,
} from '../types'
import { EMPTY_CONSTRAINTS } from '../lib/constraints'

interface State {
  fileId?: string
  courses: Course[]
  selected: string[] // course_code đã chọn

  constraints: OptimizerConstraints
  parseStatus?: ParseStatus
  issues: PreferenceIssue[]

  options: TimetableOption[]
  stats?: OptimizeStats
  activeIdx: number
  hasRun: boolean
  loading: boolean
  optimizeError: string | null

  setUpload: (fileId: string) => void
  setCourses: (c: Course[]) => void
  toggleCourse: (code: string) => void
  selectAll: (all: boolean) => void
  setParsed: (r: PreferenceParseResult) => void
  setConstraints: (c: OptimizerConstraints) => void
  setResult: (r: OptimizeResponse) => void
  setActiveIdx: (i: number) => void
  setLoading: (b: boolean) => void
  setOptimizeError: (msg: string | null) => void
  reset: () => void
}

const CLEAN_RESULT = {
  options: [] as TimetableOption[],
  stats: undefined,
  activeIdx: 0,
  hasRun: false,
  optimizeError: null,
}

// Chỉ lưu file/môn học vào localStorage để F5 trang /plan không mất dữ liệu.
export const useApp = create<State>()(
  persist(
    (set) => ({
      courses: [],
      selected: [],
      constraints: EMPTY_CONSTRAINTS,
      issues: [],
      loading: false,
      ...CLEAN_RESULT,

      setUpload: (fileId) => set({ fileId }),
      setCourses: (courses) =>
        set({ courses, selected: courses.map((c) => c.course_code), ...CLEAN_RESULT }),
      toggleCourse: (code) =>
        set((s) => ({
          selected: s.selected.includes(code) ? s.selected.filter((c) => c !== code) : [...s.selected, code],
        })),
      selectAll: (all) => set((s) => ({ selected: all ? s.courses.map((c) => c.course_code) : [] })),

      setParsed: (r) => set({ constraints: r.constraints, parseStatus: r.status, issues: r.issues }),
      setConstraints: (constraints) => set({ constraints }),

      setResult: (r) =>
        set({ options: r.options, stats: r.stats, activeIdx: 0, hasRun: true, optimizeError: null }),
      setActiveIdx: (activeIdx) => set({ activeIdx }),
      setLoading: (loading) => set({ loading }),
      setOptimizeError: (optimizeError) => set({ optimizeError, hasRun: true }),

      reset: () =>
        set({
          fileId: undefined,
          courses: [],
          selected: [],
          constraints: EMPTY_CONSTRAINTS,
          parseStatus: undefined,
          issues: [],
          loading: false,
          ...CLEAN_RESULT,
        }),
    }),
    {
      name: 'tkb-ai-store',
      partialize: (s) => ({ fileId: s.fileId, courses: s.courses, selected: s.selected }),
    },
  ),
)