---
name: cbeta
description: 中华电子佛典智能助手。当用户引用佛经句子询问出处、使用「出处」「来源」「CBETA引用」关键词、查询佛经内容、提供佛经片段要求确认来源、询问某句话出自哪部经典、需要标准学术引用格式、搜索佛教相关文本、使用「般若」「金刚」「法华」「阿含」等佛经关键词、提供经号查询、需要简繁转换（佛经语境）时，**必须触发此 skill**，即使用户没有明确说「CBETA」。
---

# CBETA 中华电子佛典智能助手

## 核心能力

CBETA Skill 提供中华电子佛典协会（Chinese Buddhist Electronic Text Association）API 的完整封装，支持：

1. **智能出处查找** - 输入佛经句子，自动生成标准 CBETA 引用格式
2. **智能搜索** - 自动简繁转换，标准/模糊/布尔/KWIC 搜索
3. **佛典信息查询** - 经号、标题、译者、时代、字数、卷数
4. **全文获取** - 指定卷号获取经文内容
5. **关键词定位** - 精确页码栏行号定位（支持去标点匹配）
6. **数据导出** - 导出佛典列表、作译者、朝代统计等

### 新增功能（2026-04）

| 功能 | 描述 | 性能提升 |
|------|------|----------|
| 精确页码定位 | 搜索结果无 `lb` 时自动调用 KWIC 补全页码 | 100% 页码覆盖率 |
| 异步并发批量 | `batch_find_sources_async` 并发查询多个关键词 | 2.8x 加速 |
| CLI batch 命令 | `search batch` 批量出处查找 | 支持摘要/JSON输出 |
| 配置文件系统 | `CbetaConfig` 类支持 JSON/YAML 配置持久化 | - |

---

## 基础设施

### 缓存机制

Skill 内置内存缓存，减少重复请求：
- 缓存有效期：1小时（3600秒）
- 缓存键：MD5(端点+参数)
- 自动失效：过期自动清理

### 重试机制

网络异常自动重试：
- 最大重试次数：3次
- 递增延迟：1秒 → 2秒 → 3秒
- 覆盖场景：连接超时、服务器错误、临时故障

### 请求限制

Rate Limiter 防止 API 过载：
- 限制：每秒最多 10 次请求
- 实现：线程安全锁，自动等待间隔
- 目的：保护 API 服务稳定性

### 快速页码映射

常见经文预置页码映射表（25部），加速定位：
- 金刚经、心经、法华经、华严经、涅槃经等
- 无需调用 goto API，直接计算行首信息
- 减少网络请求，提升响应速度

### 配置系统

`CbetaConfig` 类支持持久化配置：

**默认配置**：
```python
DEFAULT_CONFIG = {
    "cache_dir": None,           # 缓存目录（None=内存缓存）
    "cache_expire_seconds": 3600, # 缓存有效期
    "timeout": 30,               # 请求超时秒数
    "max_retries": 3,            # 最大重试次数
    "retry_delay": 1.0,          # 重试延迟基数
    "rate_limit": 10,            # 每秒请求限制
    "max_concurrent": 5,         # 最大并发数
    "default_rows": 20,          # 默认搜索结果数
}
```

**使用方式**：
```python
# 从文件加载配置
config = CbetaConfig.load("config.json")
api = CbetaAPI(config=config)

# 保存配置到文件
config.save("config.yaml")
```

**支持格式**：JSON、YAML

---

## 快速使用

### 出处查找（最常用）

用户输入佛经句子，skill 自动：
1. 简繁转换
2. 搜索定位
3. 生成标准引用格式

**示例输入**：
- "应无所住而生其心出自哪里"
- "色即是空出自什么经"
- "一切有为法如梦幻泡影的出处"

**标准输出格式**：
```
《经名》：「引用文」(CBETA 版本, 册号, no. 经号, p. 页码栏行)

例: 《金刚般若波罗蜜经》：「应无所住而生其心」(CBETA 2025.R3, T08, no. 235, p. 749c22-23)
```

---

## API 接口速查

### Base URL
备选 URL（自动切换）：
1. `https://cbdata.dila.edu.tw/stable/` (官方新端点)
2. `https://api.cbetaonline.cn` (旧端点，部分网络可用)

### 核心端点

| 功能 | 端点 | 关键参数 | 备注 |
|------|------|----------|------|
| 全文搜索 | `/search` | q, rows, canon, category, order | ✅ |
| 布尔搜索 | `/search/extended` | q(双引号), AND/OR/NOT | ✅ |
| 模糊搜索 | `/search/fuzzy` | q | ❌ 新API不可用 |
| KWIC搜索 | `/search/kwic` | q, work, juan, note, mark | ✅ 已修复 |
| 佛典信息 | `/works` | work | ✅ |
| 卷定位 | `/juans/goto` | canon, work, juan | ✅ |
| 行内容 | `/lines` | linehead_start, linehead_end | ✅ |
| 简繁转换 | `/chinese_tools/sc2tc` | q | ✅ |
| 分词 | `/word_seg2` | payload | ✅ |
| 导出佛典 | `/export/all_works` | - | ✅ |
| 导出作译者 | `/export/all_creators2` | - | ✅ |
| 健康检查 | `/health` | - | ✅ |
| 统计报表 | `/report/total` | - | ✅ |

### Linehead 格式
`T08n0235_p0749c22` = 册号n经号_p页码栏行

栏位：a=上栏, b=中栏, c=下栏

---

## 出处查找流程

执行出处查找时，按以下步骤操作：

1. **简繁检测** - 检查输入是否含简体字（应、无、经等）
2. **调用 sc2tc** - `/chinese_tools/sc2tc?q={输入}` 转换繁体
3. **搜索** - `/search?q={繁体}&rows=20&order=time_from+`
4. **识别经本** - 筛选标题以「经」结尾，排除注疏词（註疏論義記解釋）
5. **获取全文** - goto API 获取起始行号，lines API 获取内容
6. **关键词定位** - 去标点匹配，定位精确行号
7. **精确页码补全** - 若搜索结果无 `lb` 字段，自动调用 KWIC 获取精确页码
8. **生成引用** - 按标准格式输出

### 精确页码定位（新增）

当搜索结果缺少 `lb` 字段时，`find_source` 自动调用 KWIC API 补全页码：

```python
# 搜索结果无 lb 时自动触发
if not lb:
    tc_keyword = self.sc2tc(keyword)
    kwic_result = self.search_kwic(tc_keyword, work=work, juan=juan)
    if kwic_result.get("num_found") > 0:
        lb = kwic_result["results"][0].get("lb", "")
```

**效果**：100% 页码覆盖率，确保引用格式完整

### 关键实现细节

**经本筛选逻辑**：
```python
def is_sutra(work_title):
    # 标题以「经」结尾
    if not title.endswith('經'):
        return False
    # 排除注疏
    exclude_words = ['註', '疏', '論', '義', '記', '解', '釋']
    for word in exclude_words:
        if word in title:
            return False
    return True
```

**去标点匹配**：
```python
# 用户输入可能无标点，经文有标点
# 去除匹配时忽略标点差异
import re
text_clean = re.sub(r'[，。、；：？！「」『』（）]', '', full_text)
keyword_clean = re.sub(r'[，。、；：？！「」『』（）]', '', keyword)
```

**页码解析**：
```python
# linehead: T08n0235_p0749c22
# 解析为: 册8, 经235, 页749, 下栏22行
parts = linehead.split('_')
# T08n0235 → canon=T, vol=08, work=0235
# p0749c22 → page=749, col=c, line=22
```

---

## 搜索参数详解

### 藏经筛选 (canon)
| 代码 | 名称 | 数量 |
|------|------|------|
| T | 大正藏 | 2,457 |
| X | 新纂卍续藏 | 1,230 |
| N | 南传大藏经 | 38 |
| K | 高丽藏 | 9 |

### 部类筛选 (category)
22类：
- 般若部类、阿含部类、本缘部类、法华部类、华严部类
- 宝积部类、涅槃部类、大集部类、经集部类、密教部类
- 律部类、毘昙部类、中观部类、瑜伽部类、论集部类
- 净土宗部类、禅宗部类、史传部类、事汇部类
- 敦煌写本部类、国图善本部类、南传大藏经部类、新编部类

### 排序选项 (order)
- `time_from+` - 按成立年代升序（找最早出处）
- `term_hits-` - 按词频降序
- `work+` - 按经号排序

---

## 布尔搜索语法

| 运算 | 语法 | 示例 |
|------|------|------|
| AND | "词1" "词2" | `"般若" "金刚"` |
| OR | "词1" \| "词2" | `"波羅蜜" \| "波羅密"` |
| NOT | "词1" !"排除" | `"迦葉" !"迦葉佛"` |
| NEAR | "词1" NEAR/n "词2" | `"老子" NEAR/7 "道"` |

---

## 引用格式规范

### 标准格式
```
《经名》：「引用文」(CBETA 版本, 册号, no. 经号, p. 页码栏行)
```

### 版本信息
- CBETA 2025.R3（当前最新）

### 页码格式
- 单行：`p. 749c22`
- 跨行：`p. 749c22-23`
- 跨栏：`p. 749c22-b05`
- 跨页：`pp. 749c22-750a05`

### 经号格式
- 册号：`T08`（大正藏第8册）
- 经号：`no. 235` 或 `no. 0235`

---

## 快速定位代码

| 代码 | 经典 | 经号 |
|------|------|------|
| SA | 杂阿含 | T02n0099 |
| MA | 中阿含 | T01n0026 |
| DA | 阿含 | T01n0001 |
| EA | 增壹阿含 | T02n0125 |
| SN | 相应部 | N13n0006 |

---

## 输出模板

### 出处查找结果
```markdown
## 出处查找结果

**关键词**: [用户输入]

### 原始出处
- **经典**: [经名] ([经号])
- **译者**: [译者信息]
- **时代**: [朝代] ([年份])
- **藏经**: [藏经代码] ([册号])

### 标准 CBETA 引用格式
《[经名]》：「[引用文]」(CBETA [版本], [册号], no. [经号], p. [页码])

### 其他出处
[如有多个出处，按时间排序]
```

### 搜索结果
```markdown
## 搜索结果

**关键词**: [关键词]
**结果数**: [数量] 卷，词频 [次数]

| 序号 | 经号 | 经名 | 词频 | 时代 |
|------|------|------|------|------|
| 1 | T0235 | 金刚般若波罗蜜经 | 3 | 后秦 |
```

### 佛典信息
```markdown
## 佛典信息

- **经号**: T0235
- **经名**: 金刚般若波罗蜜经
- **部类**: 般若部类
- **译者**: 后秦 鸠摩罗什译
- **时代**: 后秦 (402-412)
- **卷数**: 1
- **字数**: 8,234 字
```

---

## KWIC 搜索（关键词上下文）

KWIC (Keyword In Context) 搜索显示关键词及其上下文，用于精确定位和内容展示。

### 使用方式

```python
# 基础 KWIC 搜索
api.search_kwic("应无所住", work="T0235", around=10)

# 指定卷号的 KWIC（支持 NEAR 语法）
api.kwic_juan('"老子" NEAR/7 "道"', work="T0001", juan=1)

# 扩展 KWIC（多关键词）
api.kwic_extended(["般若", "金刚"], work="T0235")
```

### 返回字段

- `linehead`: 行首信息（含页码栏行）
- `text`: 关键词上下文文本
- `keyword`: 匹配的关键词
- `position`: 在卷中的位置

### NEAR 语法

查找两个词在指定距离内出现的段落：
```
"词1" NEAR/n "词2"  # 两词相距不超过 n 行
"老子" NEAR/7 "道"   # 查找「老子」和「道」相距7行内
```

---

## 导出方法

批量导出 CBETA 数据，用于统计分析或离线处理。

### 可用方法

| 方法 | 返回内容 | 数量 |
|------|----------|------|
| `export_all_works()` | 全部佛典列表 | 4,868 部 |
| `export_all_creators()` | 作译者列表 | - |
| `export_all_creators2()` | 作译者（含别名） | - |
| `export_dynasty()` | 朝代统计 | CSV 格式 |
| `export_dynasty_works()` | 朝代-作品关联 | - |
| `export_check_list(canon)` | 检查清单 | CSV 格式 |

### 示例

```python
# 导出全部佛典
works = api.export_all_works()
# 返回: [{"work": "T0001", "title": "長阿含經", "juan": 22}, ...]

# 导出朝代统计
dynasty_csv = api.export_dynasty()
# 返回 CSV 字符串

# 导出某藏经检查清单
check_list = api.export_check_list("J")  # 日本佛寺志
```

---

## CLI 工具

CBETA CLI 工具已安装在 `C:\Python314\Lib\site-packages\cli_anything\cbeta\`

**调用方式**：
```bash
python -m cli_anything.cbeta search source "应无所住而生其心"
python -m cli_anything.cbeta search query "般若" --rows 10
python -m cli_anything.cbeta work info T0235
```

**核心命令**：
- `search source` - 出处查找 + 标准引用
- `search smart` - 智能搜索（自动转繁+自动选模式）
- `search batch` - 批量出处查找（并发执行，2.8x 加速）
- `work info` - 佛典信息
- `work content` - 获取全文

### 批量搜索命令（新增）

```bash
# 批量出处查找
python -m cli_anything.cbeta search batch "应无所住" "色即是空" "一切有为法"

# 指定并发数
python -m cli_anything.cbeta search batch "关键词1" "关键词2" -c 5

# JSON 输出
python -m cli_anything.cbeta search batch "关键词1" "关键词2" -j

# 汇总模式
python -m cli_anything.cbeta search batch "关键词1" "关键词2" --summary
```

**参数说明**：
| 参数 | 说明 |
|------|------|
| `-c, --concurrent` | 并发数（默认3） |
| `-j, --json` | JSON 格式输出 |
| `-s, --summary` | 汇总模式，显示成功/失败统计 |

---

## 批量查找（并发模式）

API 支持异步并发批量查找，显著提升效率：

### Python API

```python
# 同步批量（使用线程池）
results = api.batch_find_sources_concurrent(
    ["应无所住", "色即是空", "一切有为法"],
    rows=10,
    max_concurrent=5
)

# 异步批量（使用 asyncio）
results = await api.batch_find_sources_async(
    ["关键词1", "关键词2"],
    max_concurrent=3
)
```

### 性能对比

| 模式 | 3个关键词耗时 | 5个关键词耗时 |
|------|-------------|-------------|
| 串行 | ~15秒 | ~25秒 |
| 并发(3) | ~5.4秒 | ~9秒 |
| 加速比 | 2.8x | 2.8x |

---

## 参考

详细API文档见 `references/` 目录：
- `api_endpoints.md` - 完整API端点列表
- `citation_format.md` - 引用格式详解
- `canon_codes.md` - 藏经代码对照表

---

*CBETA API 版本 3.6.9，资料版本 2025.R3*