# dict-cli 扩展路线

## 项目定位

终端内的英语学习工作流工具。核心原则：**不离开命令行**，在所有开发场景中无缝嵌入英语练习。

---

## 当前状态（2026-04）

- `dict-cli lookup <word>` — 有道查词，含音标/释义/发音
- AI 音节划分 → `·` 分隔 + 重音高亮（`main.py:50-63`）
- 音频播放（有道 + edge-tts 备用）
- SQLite 缓存查词结果（`dictionary.db`）

---

## 三个扩展方向

### 方向 1：写作助手（Writing Assistant）

**场景**：写 commit message 和代码注释时，中英文混杂，不知道地道表达。

```
dict fmt "修复了用户登录时的一个bug"
→ fix: resolve user login failure on token expiry

git diff | dict commit
→ feat: add pagination to search results

dict comment "遍历列表并过滤空值"
→ # Iterate through the list and filter out empty values
```

- `dict fmt` — 中译英改写，输出地道英文
- `dict commit` — 读取 git diff，输出 conventional commit 格式
- `dict comment` — 选中代码区域，生成英语注释
- 集成 git hooks（prepare-commit-msg）自动触发

### 方向 2：英语陪练（Practice / Tutor）

**场景**：工作间隙练习句子，AI 根据水平出题、纠错、解释。

```
dict practice
→ [Level: Intermediate]
→ Translate: "这个功能需要在下周前完成"
  This feature needs to be completed before next week ✓
→ Let's make it more natural:
  "This feature needs to be shipped by next week"
```

子模式：
- 中译英 → AI 纠正并解释
- 句子改写 → 更地道/更简洁
- 完形填空 → 工作场景常见表达
- 自由对话 → 模拟 code review / standup

### 方向 3：间隔复习（Spaced Repetition）

**场景**：查过的词不复习等于白查。按 SM-2 算法排期，到时间提醒复习。

```
dict review
→ 3 due today. (difficulty: hard)
  mitigate: v. 减轻，缓和
  Show answer? [Y/n]
  → We need to mitigate the risk...
  How well did you know? (1-4)
```

- 查词时自动加入复习队列
- SM-2 算法计算下次复习时间
- 复习时展示例句、词根，加深记忆

---

## 数据存储策略

### 原则

- **SQLite 做主存储**：结构化数据、关系查询、版本迁移都方便
- **Markdown 做按需导出**：复习笔记可以导出为 Markdown，喂给思源笔记 MCP
- **不锁定任何平台**：数据在自己手里，Web/MCP 都是消费端

### Schema

详见 [schema.md](schema.md)

---

## 实施阶段

| 阶段 | 内容 | 依赖 |
|------|------|------|
| **Phase 0** | 重构 AI 层为通用 AIService + 新 Schema 落地 | 无 |
| **Phase 1** | 查词增强（例句/词根/搭配） | Phase 0 |
| **Phase 2** | 写作助手（fmt commit/comment） | Phase 0 |
| **Phase 3** | 练习模式（practice） | Phase 0 + Phase 1 |
| **Phase 4** | 间隔复习（review queue，SM-2） | Phase 1（数据积累） |
| **Phase 5** | Web 界面 | 所有 Phase |

---

## 架构变化

```
当前                              扩展后
─────                            ─────
main.py → DictionaryService     main.py ℹ─→ DictionaryService (有道)
       → SyllableService                 ├─→ AIService ─┬─→ SyllableService (音节)
       → AudioService                    │              ├─→ FmtService (写作助手)
                                         │              ├─→ TutorService (陪练)
                                         │              └─→ EnrichmentService (例句/词根)
                                         ├─→ AudioService (播放)
                                         └─→ ProfileService (用户画像 → SQLite)
```

AIService 封装 API 调用/重试/provider 切换；各子模块只负责 prompt 构造和结果解析。
