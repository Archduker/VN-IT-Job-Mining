# Quy trình Git: feature và hotfix

Nguồn quy tắc: `docs/tasks/README.md` (mục 2, 3), `docs/spec/12_coding_standards.md` (mục 5), `docs/CLAUDE.md`. Mục nào ghi **(đề xuất)** là quy tắc mới, chưa có trong tài liệu gốc, cần Lead (Thuận) chốt.

## 1. Sơ đồ nhánh

```
main                       <- chỉ Lead (Thuận) merge từ sprint
 └─ sprint/pipeline-delivery   <- nhánh tích hợp của sprint
     ├─ feature/<tên-nhánh>    <- việc trong sprint, mỗi người một nhánh (bảng 8 thành viên)
     └─ hotfix/<mô-tả-ngắn>    <- sửa lỗi gấp, tách từ sprint, merge lại vào sprint
```

- Cả feature và hotfix đều **tách từ và merge vào `sprint/pipeline-delivery`**. Không ai merge vào `main` trừ Lead.
- Quy ước commit (theo `git log`): `type(scope): mô tả tiếng Việt`, ví dụ `fix(collection): sửa ...`, `docs(spec): ...`, `preprocessing: ...`. Kiểu dùng: `feat`, `fix`, `docs`, `test`, `refactor`.

## 2. Khi nào dùng hotfix, khi nào dùng feature

| Tình huống | Dùng |
|---|---|
| Việc đã giao trong `docs/tasks/0X_*.md` | `feature/<nhánh của bạn>` (đã có trong bảng task) |
| Lỗi làm hỏng pipeline, test đỏ trên sprint, crawler sai dữ liệu, cần sửa nhỏ và gấp, không chờ hết nhiệm vụ | `hotfix/<mô-tả-ngắn>` |
| Tính năng mới, refactor, sửa lớn nhiều thư mục | feature, không dùng hotfix |

Hotfix chỉ chứa **một lỗi, diff nhỏ** (đề xuất). Lỗi nằm trong thư mục của người khác thì báo chủ thư mục hoặc Lead, xem mục 6.

Đặt tên: `hotfix/<mô-tả-ngắn>`, chữ thường, gạch nối, không dấu. Ví dụ `hotfix/topcv-ledger-merge`, `hotfix/monitoring-sse-log`.

## 3. Các bước làm hotfix

```bash
# 1. Lấy bản mới nhất, tách nhánh từ remote sprint
git fetch origin
git checkout -b hotfix/<mô-tả-ngắn> origin/sprint/pipeline-delivery

# 2. Sửa lỗi + viết test hồi quy (test fail trước khi sửa, pass sau khi sửa)
#    Chỉ format/sửa ruff trên dòng mình đổi (docs/spec/12), không format diện rộng.

# 3. Kiểm tra
make test-fast
pytest tests/contract/<test_liên_quan>.py     # nếu sửa crawler (chuẩn C1-C14)
pytest tests/unit/<test_liên_quan>.py::<test>  # test hồi quy vừa thêm

# 4. Ghi nhật ký lỗi (docs/CLAUDE.md, docs/spec/12 mục 5)
#    - Thêm mục L-<số tiếp theo> vào docs/issue_log.md: Lỗi / Nguyên nhân / Cách xử lý / Còn lại / Kiểm chứng
#    - Xóa mục tương ứng khỏi KNOWN_ISSUED.md (nếu có)
#    - Lỗi dễ lặp lại: thêm 1 dòng vào CLAUDE.md của thư mục chứa lỗi

# 5. Commit và push
git add <file đã đổi> docs/issue_log.md KNOWN_ISSUED.md
git commit -m "fix(<module>): <mô tả lỗi đã sửa> (L-<số>)"
git push -u origin hotfix/<mô-tả-ngắn>
```

6. Mở Pull Request trên GitHub: base = `sprint/pipeline-delivery`. Mô tả PR ghi: lỗi gì, nguyên nhân, test nào chứng minh, mã `L-xx`.
7. Review: Lead Thuận review theo `docs/tasks/README.md`. **(đề xuất)** hotfix cần ít nhất 1 reviewer; nếu người sửa là Thuận thì nhờ 1 thành viên khác review.
8. Merge: **(đề xuất)** dùng squash merge để mỗi hotfix là một commit trên sprint, dễ revert. Tài liệu hiện chưa quy định kiểu merge; Lead chốt.
9. Sau khi merge, xóa nhánh hotfix trên remote do Lead/người tạo thực hiện.

Không đụng `.env` và R2 trong lúc sửa. Ghi hoặc xóa trên R2 phải chạy dry-run trước và cần người dùng đồng ý (CLAUDE.md gốc).

## 4. Đồng bộ nhánh feature sau khi hotfix đã vào sprint

Mỗi người tự cập nhật nhánh của mình bằng **merge** (không rebase nhánh đã push, tránh viết lại lịch sử chung):

```bash
git fetch origin
git checkout feature/<nhánh-của-bạn>
git merge origin/sprint/pipeline-delivery
# có xung đột: sửa tay, chạy lại make test-fast, rồi
git commit            # nếu merge dừng vì xung đột
git push
```

Nên làm trước khi mở PR cuối tuần và mỗi khi Lead thông báo có hotfix mới.

## 5. Xung đột thư mục sở hữu

Theo `docs/tasks/README.md` mục 2: mỗi người chỉ commit trong thư mục được giao và file cẩm nang cá nhân.

- Hotfix cần sửa file ngoài thư mục của mình: **(đề xuất)** nhắn chủ thư mục, hoặc nhờ Lead cho phép trong PR. PR nêu rõ file ngoài ranh giới và lý do.
- (đề xuất) Khi merge sprint vào feature có xung đột ở thư mục của người khác: lấy bản của sprint (`git checkout --theirs <file>` hoặc `git checkout origin/sprint/pipeline-delivery -- <file>`), không tự sửa tay.
- (đề xuất) Thư mục dùng chung (`docs/issue_log.md`, `KNOWN_ISSUED.md`): xung đột chỉ là thêm mục mới thì giữ cả hai, đánh lại số `L-xx` cho khỏi trùng.

## 6. Trường hợp khẩn: chính sprint bị hỏng

1. Báo ngay cho Lead (Thuận), nêu commit/PR nghi ngờ và lệnh tái hiện (`make test-fast` đỏ ở đâu).
2. **(đề xuất)** Mọi người tạm dừng merge PR mới vào sprint cho đến khi sửa xong.
3. Cách sửa, ưu tiên theo thứ tự:
   - Hotfix nhỏ theo mục 3, review nhanh.
   - Không sửa nhanh được: revert commit gây lỗi bằng PR, không push thẳng và không force-push.
   ```bash
   git fetch origin
   git checkout -b hotfix/revert-<mô-tả> origin/sprint/pipeline-delivery
   git revert <sha>        # với merge commit: git revert -m 1 <sha>
   make test-fast && git push -u origin hotfix/revert-<mô-tả>
   ```
4. Ghi `L-xx` vào `docs/issue_log.md` như hotfix thường.
5. `main` chỉ nhận từ sprint qua Lead, nên sprint hỏng thì **không** merge sang `main`.

## 7. Nhánh `hotfix` cục bộ đã có

Trong máy hiện có nhánh local `hotfix` (commit `83f8432`, chưa có trên remote). Nó **không thuộc quy trình này** (tên không theo `hotfix/<mô-tả-ngắn>`, không tách từ `origin/sprint/pipeline-delivery`). Cách xử lý do người dùng quyết định; tài liệu này không tự đổi tên, xóa hay push nó.

## 8. Checklist trước khi mở PR hotfix

- [ ] Nhánh tách từ `origin/sprint/pipeline-delivery` mới nhất, tên `hotfix/<mô-tả-ngắn>`
- [ ] Chỉ một lỗi, diff nhỏ, chỉ sửa ruff trên dòng đã đổi
- [ ] Có test hồi quy; `make test-fast` xanh; contract test liên quan xanh (nếu sửa crawler)
- [ ] `docs/issue_log.md` có mục `L-xx` đủ 5 trường; `KNOWN_ISSUED.md` đã xóa mục tương ứng
- [ ] Không commit `.env`, không ghi/xóa R2, không dữ liệu thô lớn
- [ ] Commit theo dạng `type(scope): mô tả tiếng Việt`
- [ ] PR base = `sprint/pipeline-delivery`; đã gán reviewer
- [ ] Sau khi merge: thông báo cả nhóm để merge sprint vào nhánh feature (mục 4)
