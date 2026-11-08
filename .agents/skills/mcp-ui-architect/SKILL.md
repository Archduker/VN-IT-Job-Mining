---
name: mcp-ui-architect
description: >-
  Chuyên gia thiết kế, nâng cấp và thẩm định giao diện UI/UX hiện đại kết hợp tối ưu hóa Backend
  cho hệ thống VN-IT-Job-Mining. Chuyên sâu về: khai thác MCP shadcn-space để tìm kiếm và tích hợp
  các khối UI chuẩn mực (Dashboard cards, Data tables, Glassmorphic headers), áp dụng hiệu ứng animation
  Magic UI, tự động hóa kiểm thử giao diện qua Puppeteer MCP và tăng tốc truy vấn dữ liệu Lakehouse bằng DuckDB.
---

# MCP UI Architect Skill

Kỹ năng này trang bị cho AI Agent quy trình và phương pháp luận khai thác tối đa hệ sinh thái **Model Context Protocol (MCP)** để kiến tạo giao diện người dùng đạt chuẩn thẩm mỹ cao cấp (World-class aesthetic), mượt mà (60 FPS) và có Backend chịu tải cao cho dự án VN-IT-Job-Mining.

---

## 1. Danh Mục Các MCP Servers Được Hỗ Trợ

Hệ thống được cấu hình sẵn các công cụ MCP phục vụ cả Frontend và Backend:

1. **`shadcn-space` (`shadcnspace-mcp@latest`)**:
   - Truy vấn kho blocks, templates và components chuẩn hóa từ [shadcnspace.com](https://shadcnspace.com).
   - Loại bỏ hoàn toàn hiện tượng AI bịa code (hallucination) hoặc dùng sai props của Tailwind/Radix UI.
2. **`magic-ui` (`@21st-dev/magic-mcp@latest`)**:
   - Cung cấp các khối đồ họa tương tác cao cấp: Bento grids, viền thẻ phát sáng (glowing border cards), marquee chuyển động.
3. **`puppeteer-ui-tester` (`@modelcontextprotocol/server-puppeteer`)**:
   - Tự động mở trình duyệt Chromium ngầm, kiểm thử tương tác click, đo tỷ lệ khung hình (FPS) của đồ thị WebGL 3D và chụp ảnh màn hình nghiệm thu tự động.
4. **`duckdb-mcp`**:
   - Cho phép truy vấn SQL siêu tốc trực tiếp trên các file `.parquet` và `.jsonl` trong phân tầng Lakehouse phục vụ cho Backend API.

---

## 2. Quy Trình 5 Bước Thiết Kế UI Bằng `shadcn-space` MCP

Khi người dùng yêu cầu tạo mới hoặc nâng cấp một khối giao diện (ví dụ: Stat card, Data table, Filter layout):

### Bước 1: Khảo sát danh mục (Categories Discovery)
Gọi công cụ `listCategories` qua `call_mcp_tool` để xác định nhóm component phù hợp:
```json
{
  "ServerName": "shadcn-space",
  "ToolName": "listCategories",
  "Arguments": {}
}
```

### Bước 2: Tìm kiếm Block Miễn Phí (Search & Filter)
Gọi công cụ `searchBlocks` hoặc `listFreeBlocks` với từ khóa mong muốn (ví dụ: `stats`, `dashboard`, `table`):
```json
{
  "ServerName": "shadcn-space",
  "ToolName": "searchBlocks",
  "Arguments": {
    "query": "stats card",
    "freeOnly": true
  }
}
```

### Bước 3: Lấy Mã Cài Đặt & Cấu Trúc Code (Get Block Install)
Gọi công cụ `getBlockInstall` để lấy mã nguồn TSX, danh sách phụ thuộc và hướng dẫn nhúng chính xác:
```json
{
  "ServerName": "shadcn-space",
  "ToolName": "getBlockInstall",
  "Arguments": {
    "blockName": "stats-01"
  }
}
```

### Bước 4: Tích hợp vào Mã Nguồn Dự Án
- Đặt component vào đúng thư mục: `monitoring/frontend/src/components/<feature>/`.
- Áp dụng các token màu sắc ngữ nghĩa của dự án (Dark Slate `#090d16`, Indigo `#6366f1`, Emerald `#10b981`, Cyan `#06b6d4`).

### Bước 5: Kiểm Thử Giao Diện Tự Động (Visual Verification)
Sử dụng `puppeteer-ui-tester` để mở trang web cục bộ `http://localhost:5173`, xác nhận không có lỗi React console và giao diện hiển thị đúng mong đợi.

---

## 3. Tiêu Chuẩn Thẩm Mỹ Bắt Buộc Cho Dashboard Monitoring

Mọi màn hình do Agent thiết kế phải tuân thủ nghiêm ngặt các nguyên tắc thị giác:
1. **Glassmorphism & Depth**: Dùng `backdrop-blur-md` kết hợp màu nền trong suốt `bg-slate-900/80` và viền mảnh `border-slate-800/80` để tạo chiều sâu thị giác.
2. **Typography Rõ Ràng**: Tiêu đề in hoa mảnh (`uppercase tracking-wider text-xs font-semibold`), số liệu thống kê lớn (`text-2xl font-bold font-mono`).
3. **Màu Sắc Ngữ Nghĩa Nhất Quán**:
   - Màu xanh ngọc (Emerald): Thể hiện dữ liệu sạch, Golden Master Dataset, tiến trình thành công, kết nối Online.
   - Màu xanh lơ (Cyan): Thể hiện tác vụ tiền xử lý, dữ liệu sau regex.
   - Màu chàm tím (Indigo/Violet): Đại diện cho nền tảng, AI/ML 3D Lab.
   - Màu hổ phách (Amber): Thể hiện trạng thái cảnh báo, dữ liệu chưa đồng bộ (Out of sync).
   - Màu cánh sen đỏ (Rose): Lỗi hệ thống, bài đăng bất thường hoặc tin rác.
4. **Không Thêm Nút Đăng Nhập (Zero-Auth Principle)**: Luôn nhớ đây là Dashboard quan sát nội bộ, tuyệt đối không chèn nút Login, Sign In hay User Avatar.
5. **Thống Nhất 100% TypeScript (Strictly No JavaScript)**: Toàn bộ code sinh ra hoặc tích hợp từ MCP `shadcn-space` bắt buộc phải là TypeScript (`.ts` / `.tsx`). Nghiêm cấm nhận hoặc tạo file `.js` / `.jsx`. Mọi props, state và API responses phải được định kiểu chặt chẽ trong `types.ts`, không dùng kiểu `any`.
