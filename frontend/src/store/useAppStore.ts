import { create } from 'zustand'
import type { Course, Constraints, TimetableOption, OptimizeResponse } from '../types'

interface State {
  fileId?: string
  courses: Course[]
  selected: string[]
  constraints?: Constraints
  options: TimetableOption[]
  stats?: OptimizeResponse['stats']
  activeIdx: number
  loading: boolean
  setUpload: (fileId: string) => void
  setCourses: (c: Course[]) => void
  toggleCourse: (code: string) => void
  setConstraints: (c: Constraints) => void
  setResult: (r: OptimizeResponse) => void
  setActiveIdx: (i: number) => void
  setLoading: (b: boolean) => void
}

export const useApp = create<State>((set) => ({
  courses: [],
  selected: [],
  options: [],
  activeIdx: 0,
  loading: false,
  setUpload: (fileId) => set({ fileId }),
  setCourses: (courses) => set({ courses }),
  toggleCourse: (code) =>
    set((s) => ({
      selected: s.selected.includes(code) ? s.selected.filter((c) => c !== code) : [...s.selected, code],
    })),
  setConstraints: (constraints) => set({ constraints }),
  setResult: (r) => set({ options: r.options, stats: r.stats, activeIdx: 0 }),
  setActiveIdx: (activeIdx) => set({ activeIdx }),
  setLoading: (loading) => set({ loading }),
}))