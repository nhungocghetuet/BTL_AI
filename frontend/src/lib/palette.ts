/**
 * Màu các môn học trên lưới TKB, lấy từ bảng màu xanh.
 * Sắp xếp xen kẽ xanh ngọc, xanh tím, xanh trời, xanh xám để các môn
 * cạnh nhau dễ phân biệt. Quá 8 môn thì quay vòng.
 */
export interface CourseColor {
  bg: string
  border: string
}

export const COURSE_COLORS: CourseColor[] = [
  { bg: '#96d5de', border: '#048fae' }, // Alice Blue
  { bg: '#99a7ca', border: '#204177' }, // Roslyn's Blue
  { bg: '#55aad3', border: '#06659f' }, // Blue Note
  { bg: '#aad8d5', border: '#048fae' }, // Lake Blue
  { bg: '#bddaec', border: '#06659f' }, // Celestia
  { bg: '#4da4c0', border: '#204177' }, // Pim's Blue
  { bg: '#aabfd0', border: '#204177' }, // Lily Blue
  { bg: '#a4d7ea', border: '#0180b3' }, // Wild Blue Yonder
]