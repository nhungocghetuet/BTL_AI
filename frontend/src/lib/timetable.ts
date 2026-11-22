import type { PlacedSession } from '../types'
import { dayToNumber } from './constraints'

export interface Conflict {
  a: number // chỉ số trong mảng sessions
  b: number
  day: number
  periods: number[] // các tiết trùng
}

/** Tìm các cặp buổi học cùng thứ và có chung ít nhất 1 tiết. */
export function findConflicts(sessions: PlacedSession[]): Conflict[] {
  const out: Conflict[] = []
  for (let i = 0; i < sessions.length; i++) {
    for (let j = i + 1; j < sessions.length; j++) {
      const di = dayToNumber(sessions[i].day)
      const dj = dayToNumber(sessions[j].day)
      if (Number.isNaN(di) || di !== dj) continue
      const common = sessions[i].periods.filter((p) => sessions[j].periods.includes(p))
      if (common.length > 0) out.push({ a: i, b: j, day: di, periods: common })
    }
  }
  return out
}

export interface Placed {
  session: PlacedSession
  index: number
  day: number // 2..8
  start: number
  end: number
  lane: number // làn (cột con) khi nhiều buổi chồng nhau trong cùng 1 ngày
  lanes: number // tổng số làn của ngày đó
}

/**
 * Xếp các buổi học lên lưới. Buổi nào không xác định được thứ/tiết
 * thì đưa vào `skipped` (để UI báo, không âm thầm bỏ mất dữ liệu).
 */
export function layoutSessions(sessions: PlacedSession[]): { placed: Placed[]; skipped: PlacedSession[] } {
  const skipped: PlacedSession[] = []
  const items: Omit<Placed, 'lane' | 'lanes'>[] = []

  sessions.forEach((session, index) => {
    const day = dayToNumber(session.day)
    const valid =
      Number.isInteger(day) &&
      day >= 2 &&
      day <= 8 &&
      session.periods.length > 0 &&
      session.periods.every((p) => Number.isInteger(p) && p >= 1)
    if (!valid) {
      skipped.push(session)
      return
    }
    items.push({ session, index, day, start: Math.min(...session.periods), end: Math.max(...session.periods) })
  })

  const placed: Placed[] = []
  for (let day = 2; day <= 8; day++) {
    const list = items.filter((x) => x.day === day).sort((a, b) => a.start - b.start || a.end - b.end)
    const laneEnds: number[] = [] // tiết kết thúc của buổi cuối cùng trong mỗi làn
    const assigned = list.map((x) => {
      let lane = laneEnds.findIndex((end) => end < x.start)
      if (lane === -1) {
        lane = laneEnds.length
        laneEnds.push(x.end)
      } else {
        laneEnds[lane] = x.end
      }
      return { ...x, lane }
    })
    const lanes = Math.max(1, laneEnds.length)
    assigned.forEach((x) => placed.push({ ...x, lanes }))
  }
  return { placed, skipped }
}