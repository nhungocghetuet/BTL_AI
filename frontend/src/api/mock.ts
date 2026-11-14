import type { UploadResponse, Course, OptimizeResponse } from '../types'

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

export const mockCourses: Course[] = [
  {
    course_code: 'INT1001',
    course_name: 'Nhập môn lập trình',
    classes: [
      {
        class_code: 'INT1001-01',
        sessions: [
          { type: 'LT', day: 2, periods: [1, 2, 3], room: 'A101' },
          { type: 'TH', day: 4, periods: [7, 8], room: 'LAB2' },
        ],
      },
    ],
  },
  {
    course_code: 'MAT1002',
    course_name: 'Giải tích 1',
    classes: [
      { class_code: 'MAT1002-02', sessions: [{ type: 'LT', day: 3, periods: [9, 10], room: 'B203' }] },
    ],
  },
]

export const mockOptimize: OptimizeResponse = {
  options: [],
  stats: { solve_ms: 0, status: 'MOCK' },
}