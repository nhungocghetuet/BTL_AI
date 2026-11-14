import { useApp } from '../store/useAppStore'

export default function PlannerPage() {
  const courses = useApp((s) => s.courses)
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold">Planner (tạm)</h1>
      <p>Đã nhận {courses.length} môn từ bước upload.</p>
    </div>
  )
}