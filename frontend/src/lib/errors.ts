import axios from 'axios'

/**
 * Lấy thông báo lỗi hiển thị được từ lỗi gọi API.
 * FastAPI trả `detail` là chuỗi (HTTPException) HOẶC mảng đối tượng (lỗi 422 validate),
 * nếu đưa thẳng mảng vào JSX thì React sẽ crash, nên phải chuẩn hóa ở đây.
 */
export function getErrorMessage(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) {
    if (!e.response) {
      return 'Không kết nối được máy chủ. Hãy kiểm tra backend đã chạy chưa (hoặc máy chủ đang khởi động, thử lại sau ít phút).'
    }
    const detail = (e.response.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string' && detail) return detail
    if (Array.isArray(detail)) {
      const msgs = detail
        .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : ''))
        .filter(Boolean)
      if (msgs.length) return `Dữ liệu gửi lên không hợp lệ: ${msgs.join('; ')}`
    }
    return `${fallback} (HTTP ${e.response.status})`
  }
  return fallback
}