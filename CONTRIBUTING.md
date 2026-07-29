# 贡献指南 — 分支工作流

本项目采用**功能分支流（Feature Branch Workflow）**。`main` 分支保持稳定，所有改动通过功能分支 + Pull Request 合入。

## 分支约定

| 分支前缀 | 用途 | 示例 |
|---------|------|------|
| `feature/` | 新功能 | `feature/batch-export` |
| `fix/` | 缺陷修复 | `fix/grid-aliasing` |
| `refactor/` | 重构（不改行为） | `refactor/quantize` |
| `docs/` | 文档 | `docs/seg-research` |

## 标准流程

```bash
# 1. 从最新 main 切出功能分支
git checkout main
git pull origin main
git checkout -b feature/my-feature

# 2. 开发并提交（小而清晰的 commit）
git add -A
git commit -m "feat: 简短描述改动"

# 3. 推送功能分支
git push -u origin feature/my-feature

# 4. 开 PR 合入 main
gh pr create --base main --head feature/my-feature \
  --title "简述" --body "改动说明"

# 5. 合并后清理
git checkout main
git pull origin main
git branch -d feature/my-feature
git push origin --delete feature/my-feature
```

## Commit 信息规范

使用约定式前缀：`feat:` 新功能 / `fix:` 修复 / `refactor:` 重构 / `docs:` 文档 / `perf:` 性能 / `test:` 测试。

## 规则

- **不直接 push 到 `main`**——一律走 PR。
- PR 合入前确保应用能正常启动（`python -m py_compile` 通过、UI 可构造）。
- 一个 PR 只做一件事，保持小而专注。
