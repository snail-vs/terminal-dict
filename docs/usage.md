# dict-cli 使用说明

终端内的英语学习工作流工具。

## 安装

```bash
git clone <repo>
cd dict-cli
uv sync
```

配置 AI provider（在 `config.toml` 中）：

```toml
[ai]
default_provider = "deepseek"

[ai.providers.deepseek]
api_url = "https://api.deepseek.com/v1"
models = ["deepseek-chat"]
key_env = "DEEPSEEK_API_KEY"   # 从环境变量读取
```

## 命令一览

| 命令 | 用途 |
|------|------|
| `dict-cli <word>` | 查单词（默认命令） |
| `dict-cli lookup <word>` | 同上，显式调用 |
| `dict-cli pronounce <word>` | 播放发音（支持循环） |
| `dict-cli fmt <text>` | 中译英改写 |
| `dict-cli commit` | 生成 commit message |
| `dict-cli practice` | 交互式英语练习 |
| `dict-cli review` | 间隔复习 |
| `dict-cli serve` | 启动本地 Web 界面 |

---

## 查词

```bash
# 基本查词
dict-cli mitigate

# 指定英音
dict-cli lookup schedule --uk
```

输出示例：

```
                                 单词: mitigate                                 
┌──────┬───────────────────────────────────────────────────────────────────────┐
│ 🔊   │ 美 /ˈmɪtɪɡeɪt/                                                        │
│ 音节 │ mit·i·gate                                                            │
│ v.   │ <正式>减轻，缓和                                                      │
│ 📝   │ We added caching to mitigate the performance bottleneck.              │
│ 📝   │ Input validation helps mitigate security vulnerabilities.             │
│ 🌱   │ From Latin 'mitigare' (mitis 'soft' + agere 'to do')                  │
│ 🔗   │ mitigate risk  mitigate damage  mitigate impact                       │
└──────┴───────────────────────────────────────────────────────────────────────┘
```

- 音标：有道 API，区分美音/英音
- 音节：AI 自动划分，**重读音节粗体高亮**
- 例句/词根/搭配：AI 实时生成，首次查询后缓存

---

## 发音

```bash
# 播放美音（默认）
dict pronounce hello

# 英音
dict pronounce schedule --uk

# 循环播放 3 遍
dict pronounce definitely --loop 3

# 循环播放，自定义间隔（默认 1 秒）
dict pronounce particularly -l 5 -d 2
```

音频来源：有道词典在线语音，自动缓存到 `audio_cache/`。

---

## 写作助手

### fmt — 中译英改写

```bash
# 自动类型（默认）
dict fmt "修复了用户登录时的一个bug"
→ Fixed a bug when users log in.

# 指定输出类型
dict fmt -t commit "添加分页功能"
→ feat: add pagination functionality

dict fmt -t comment "遍历列表并过滤空值"
→ // Iterate through the list and filter out empty values

dict fmt -t translate "这个功能需要在下周前完成"
→ This feature needs to be completed before next week.
```

### commit — 生成 commit message

```bash
# 从暂存区 diff 生成
dict commit

# 包含工作区所有变更
dict commit --all

# 生成后复制到剪贴板
dict commit --copy
```

- 读取 `git diff` + AI 生成 conventional commit message
- 自动尝试 staged → unstaged → 上次 commit diff
- 历史记录写入数据库

---

## 练习模式

```bash
# 中译英练习（默认）
dict practice

# 改错练习
dict practice -m correct

# 自由对话
dict practice -m dialogue
```

交互示例：

```
开始练习! 模式: 中译英
当前水平: intermediate
输入 q 退出

📝 题目:
"我们需要在部署之前测试这个功能。"
> We need to test this feature before deployment.

✓ 正确!
This is a natural, correct translation.

📝 题目:
"这个补丁修复了三个安全漏洞。"
>
```

- 三道模式可选：中译英 / 改错 / 自由对话
- `/level <level>` 运行时切换水平（beginner / intermediate / advanced）
- 每道题记录错误标签（preposition / tense / article / word_choice ...）
- 练习结束自动建议升级

---

## 间隔复习

```bash
# 开始复习
dict review

# 指定本次复习数量
dict review -n 5
```

交互示例：

```
间隔复习 今日待复习: 3 个

1/3  implement
按回车显示答案...

  美/ˈɪmplɪment/
  音节: im·ple·ment
  [v.] 执行；贯彻；实施
  📝 We need to implement the new authentication module by Friday.

记得如何?
  [1]完全忘了 [2]部分记得 [3]想了一会儿 [4]立刻想起
> 4
✓ 4天后再次复习
```

- **查词时自动加入**复习队列
- SM-2 算法计算下次复习时间
- 四级自评调整间隔

---

## Web 界面

```bash
# 启动本地服务器
dict-cli serve

# 指定端口
dict-cli serve -p 3000
```

打开 `http://127.0.0.1:8080`：

| 页面 | 内容 |
|------|------|
| 仪表盘 | 查词统计、练习分数、待复习数 |
| 单词 | 搜索、浏览所有查过的单词 |
| 单词详情 | 音标/音节/释义/例句/词根/复习状态 |
| 练习 | 练习历史、每题记录 |
| 复习 | 待复习队列、即将到期 |

---

## 数据

所有数据存储在 `dictionary.db`，包括：

- 查词记录及有道原始响应
- 音节划分（AI 生成）
- 例句、词根、搭配（AI 生成）
- 写作助手历史
- 练习记录（每题、每题错误标签）
- 复习队列（SM-2 参数）

导出方式（后续会做）：

```bash
# 待实现
dict export --format markdown  # 导出复习笔记
dict export --format json      # 导出全量数据
```

---

## 快捷键（练习模式）

| 输入 | 作用 |
|------|------|
| `q` / `quit` / `exit` | 退出当前练习 |
| `/level <level>` | 切换水平 |
| `Enter` | 确认答案 |
| `Ctrl-C` | 强制退出 |

## 依赖

- Python >= 3.13
- 播放器：mpv / ffplay / mpg123（音频播放，可选）
- 剪贴板：xclip / xsel / pbcopy（`commit --copy`，可选）
