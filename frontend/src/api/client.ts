import axios from 'axios'
import type { UploadResponse, Course, Constraints, OptimizeResponse } from '../types'
import { mockCourses, mockOptimize, mockUpload } from './mock'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000' })
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export async function uploadFile(file: File): Promise<UploadResponse> {
  if (USE_MOCK) {
    await sleep(800)
    return mockUpload
  }
  const fd = new FormData()
  fd.append('file', file)
  return (await api.post('/upload', fd)).data
}

export async function confirmMapping(
  file_id: string,
  mapping: Record<string, string | null>,
): Promise<{ courses: Course[] }> {
  if (USE_MOCK) {
    await sleep(600)
    return { courses: mockCourses }
  }
  return (await api.post('/upload/confirm', { file_id, mapping })).data
}

export async function parsePreferences(text: string): Promise<Constraints> {
  if (USE_MOCK) {
    await sleep(500)
    return { hard: [], soft: [], summary: 'Mock: ' + text }
  }
  return (await api.post('/parse-preferences', { text })).data
}

export async function optimize(course_ids: string[], constraints: Constraints): Promise<OptimizeResponse> {
  if (USE_MOCK) {
    await sleep(800)
    return mockOptimize
  }
  return (await api.post('/optimize', { course_ids, constraints })).data
}