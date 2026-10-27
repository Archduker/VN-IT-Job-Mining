#!/usr/bin/env bash
# ==============================================================================
# SCRIPT TỰ ĐỘNG HÓA XUẤT SLIDE THUYẾT TRÌNH (MARP CLI AUTOMATION)
# Dự án: VN-IT-Job-Mining
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRESENTATION_DIR="$(dirname "$SCRIPT_DIR")"
SLIDE_MD="$PRESENTATION_DIR/slide_deck_preprocessing.md"

OUTPUT_HTML="$PRESENTATION_DIR/VN_IT_Job_Preprocessing.html"
OUTPUT_PPTX="$PRESENTATION_DIR/VN_IT_Job_Preprocessing.pptx"
OUTPUT_PDF="$PRESENTATION_DIR/VN_IT_Job_Preprocessing.pdf"

echo "======================================================================"
echo "    BỘ CÔNG CỤ TỰ ĐỘNG HÓA XUẤT SLIDE THUYẾT TRÌNH - VN-IT-JOB-MINING"
echo "======================================================================"
echo "File đầu vào: $SLIDE_MD"
echo ""

if ! command -v npx &> /dev/null; then
    echo "[-] Lỗi: Không tìm thấy 'npx' trong hệ thống. Vui lòng cài đặt Node.js."
    exit 1
fi

ACTION="${1:-all}"

case "$ACTION" in
    html)
        echo "[*] Đang xuất slide ra định dạng HTML (Trình chiếu web)..."
        npx --yes @marp-team/marp-cli "$SLIDE_MD" --html -o "$OUTPUT_HTML"
        echo "[+] Hoàn tất: $OUTPUT_HTML"
        ;;
    pptx)
        echo "[*] Đang xuất slide ra định dạng PowerPoint (.pptx)..."
        npx --yes @marp-team/marp-cli "$SLIDE_MD" --pptx -o "$OUTPUT_PPTX"
        echo "[+] Hoàn tất: $OUTPUT_PPTX"
        ;;
    pdf)
        echo "[*] Đang xuất slide ra định dạng PDF (Bản in chất lượng cao)..."
        npx --yes @marp-team/marp-cli "$SLIDE_MD" --pdf --allow-local-files -o "$OUTPUT_PDF"
        echo "[+] Hoàn tất: $OUTPUT_PDF"
        ;;
    watch|preview)
        echo "[*] Khởi động chế độ Live Preview (Vừa gõ Markdown vừa xem slide tự cập nhật)..."
        npx --yes @marp-team/marp-cli -s "$PRESENTATION_DIR"
        ;;
    all)
        echo "[1/3] Đang xuất slide ra HTML..."
        npx --yes @marp-team/marp-cli "$SLIDE_MD" --html -o "$OUTPUT_HTML"
        
        echo "[2/3] Đang xuất slide ra PowerPoint (.pptx)..."
        npx --yes @marp-team/marp-cli "$SLIDE_MD" --pptx -o "$OUTPUT_PPTX"
        
        echo "[3/3] Đang kiểm tra xuất PDF (nếu có Chromium)..."
        if npx --yes @marp-team/marp-cli "$SLIDE_MD" --pdf --allow-local-files -o "$OUTPUT_PDF" 2>/dev/null; then
            echo "[+] Xuất PDF thành công: $OUTPUT_PDF"
        else
            echo "[!] Ghi chú: Xuất PDF cần trình duyệt Chrome/Chromium không đầu. Bạn có thể mở file HTML và bấm Ctrl+P để lưu PDF."
        fi

        echo ""
        echo "======================================================================"
        echo "[+] TẤT CẢ FILE ĐÃ ĐƯỢC XUẤT THÀNH CÔNG VÀO THƯ MỤC:"
        echo "    $PRESENTATION_DIR"
        echo "    - File HTML:  $OUTPUT_HTML"
        echo "    - File PPTX:  $OUTPUT_PPTX"
        echo "======================================================================"
        ;;
    *)
        echo "Cú pháp sử dụng: $0 [all|html|pptx|pdf|preview]"
        exit 1
        ;;
esac
