# CBETA API 端点完整文档

**Base URL**: `https://cbdata.dila.edu.tw/stable/`（官方新端点，优先使用）
**备用 URL**: `https://api.cbetaonline.cn`（旧端点，部分网络可用）
**API 版本**: 3.6.9
**资料版本**: 2025.R3

---

## 目录

1. [搜索类 API](#搜索类-api)
2. [佛典类 API](#佛典类-api)
3. [行内容类 API](#行内容类-api)
4. [目录类 API](#目录类-api)
5. [工具类 API](#工具类-api)
6. [导出类 API](#导出类-api)
7. [服务器类 API](#服务器类-api)

---

## 搜索类 API

### 1. 全文搜索 `/search`

**状态**: ✅ 正常工作

**参数**:
| 参数名 | 必填 | 说明 |
|--------|------|------|
| q | 必须 | 搜寻字词，可含组字式 |
| rows | 可选 | 每页笔数，预设20 |
| start | 可选 | 分页起始位置，预设0 |
| order | 可选 | 排序栏位，最多5个 |
| fields | 可选 | 指定回传栏位 |
| canon | 可选 | 藏经筛选 (T, X, K 等) |
| category | 可选 | 部类筛选 |
| dynasty | 可选 | 朝代筛选 |
| work | 可选 | 佛典编号 |

---

### 2. 布尔搜索 `/search/extended`

**状态**: ✅ 正常工作

**语法**:
| 运算 | 格式 | 示例 |
|------|------|------|
| AND | `"词1" "词2"` | `"般若" "金刚"` |
| OR | `"词1" | "词2"` | `"波羅蜜" | "波羅密"` |
| NOT | `"词1" !"排除"` | `"迦葉" !"迦葉佛"` |
| NEAR | `"词1" NEAR/n "词2"` | `"老子" NEAR/7 "道"` |

---

### 3. 模糊搜索 `/search/fuzzy`

**状态**: ❌ 新API不可用（返回404）

**替代方案**: 使用标准 `/search` 端点即可

---

### 5. KWIC 搜索 `/search/kwic`

**状态**: ✅ 正常工作（端点已修正）

**功能**: 关键词上下文搜索，需指定 work 和 juan

**参数**:
| 参数名 | 必填 | 说明 |
|--------|------|------|
| q | 必须 | 搜索关键字（建议使用繁体） |
| work | 必须 | 佛典编号 |
| juan | 必须 | 卷号 |
| note | 可选 | 0:不含夹注, 1:含夹注(默认) |
| mark | 可选 | 0:不加标记(默认), 1:加mark标记 |

**NEAR 搜索**: `"词1" NEAR/n "词2"`

**示例URL**:
```
https://cbdata.dila.edu.tw/stable/search/kwic?work=T0235&juan=1&q=應無所住
```

---

### 5a. 卷内 KWIC `/kwic/juan`

**功能**: 指定卷号的 KWIC 搜索，支持 NEAR 语法

**参数**:
| 参数名 | 必填 | 说明 |
|--------|------|------|
| q | 必须 | 搜索关键字（支持 NEAR 语法） |
| work | 必须 | 佛典编号 |
| juan | 必须 | 卷号 |
| mark | 可选 | 0:不加标记(默认), 1:加mark标记 |

**返回字段**:
- `linehead`: 行首信息
- `text`: 关键词上下文文本
- `keyword`: 匹配的关键词

**NEAR 语法示例**:
```
"老子" NEAR/7 "道"   # 查找两词相距7行内
"般若" NEAR/10 "金刚" # 查找两词相距10行内
```

---

### 5b. 扩展 KWIC `/kwic/extended`

**功能**: 多关键词 KWIC 搜索

**参数**:
| 参数名 | 必填 | 说明 |
|--------|------|------|
| q | 必须 | 多关键词数组（逗点分隔） |
| work | 可选 | 佛典编号 |
| around | 可选 | 上下文行数（默认10） |

**返回字段**:
- 关键词列表及各自上下文
- 合并后的完整上下文片段

---

### 6. 经目搜索 `/search/toc`

**参数**: q, rows
**用途**: 搜索佛典目录结构

---

### 7. 标题搜索 `/search/title`

**参数**: q, rows
**用途**: 按标题搜索佛典

---

### 8. 注释搜索 `/search/notes`

**参数**: q, rows
**用途**: 搜索注释/夹注内容

---

### 9. 异体字搜索 `/search/variants`

**参数**: q
**返回**: 该字的异体字及出现次数

---

### 10. 相似文本 `/search/similar`

**参数**: work
**用途**: 查找相似佛典

---

### 11. 分面统计 `/search/facet`

**参数**: q, by(canon/category/dynasty)
**用途**: 统计分布情况

---

## 佛典类 API

### 1. 佛典信息 `/works`

**参数**: work (佛典编号)

**返回字段**:
| 字段 | 说明 |
|------|------|
| work | 佛典编号 |
| title | 佛典题名 |
| category | 所属部类 |
| byline | 作译者行 |
| creators | 作者/译者列表 |
| time_dynasty | 成立朝代 |
| time_from | 起始年代 |
| time_to | 结束年代 |
| cjk_chars | 中日韩文字数 |
| juan | 卷数 |
| places | 成立地点 |

---

### 2. 佛典目录 `/works/toc`

**参数**: work
**返回**: 树状目录结构 (title, juan, lb, children)

---

### 3. 卷列表 `/juans`

**参数**: work
**返回**: 该佛典所有卷信息

---

### 4. 卷定位 `/juans/goto`

**参数**:
| 参数名 | 说明 |
|--------|------|
| canon | 藏经代码 |
| work | 经号 |
| juan | 卷数 |
| page | 页数 |
| col | 栏 (a/b/c) |
| line | 行数 |
| linehead | 行首信息 |

**返回**: 起始行号 (linehead)

**快速代码**:
| 代码 | 经典 |
|------|------|
| DA | 长阿含 |
| SA | 杂阿含 |
| MA | 中阿含 |
| SN | 相应部 |

---

### 5. 字数统计 `/works/word_count`

**参数**: work
**返回**: 字数统计信息

---

## 行内容类 API

### `/lines`

**参数**:
| 参数名 | 说明 |
|--------|------|
| linehead | 单行行首 |
| linehead_start | 起始行首 |
| linehead_end | 结束行首 |
| before | 包含前几行 |
| after | 包含后几行 |

**返回字段**:
- `linehead`: 行首信息
- `html`: 该行文字（有注解会有anchor标记）
- `notes`: 注解

---

## 目录类 API

### 1. 目录条目 `/catalog_entry`

**参数**: entry (如 T01n0001)

---

### 2. 部类查询 `/category`

**参数**: category (部类名称)

---

## 工具类 API

### 1. 简繁转换 `/chinese_tools/sc2tc`

**参数**: q (简体文本)
**返回**: 纯文本（繁体）

---

### 2. 自动分词 `/word_seg2`

**参数**: payload (待分词文本)
**返回**: `{"segmented": "分词结果"}`

---

## 导出类 API

### 1. 全部佛典 `/export/all_works`

**返回**: JSON数组，每项含 work, title, juans

**数量**: 4,868 部佛典

**用途**: 获取完整佛典列表用于统计分析

---

### 2. 全部作译者 `/export/all_creators`

**返回**: JSON，含 num_found, results

**用途**: 获取作译者基本信息列表

---

### 3. 作译者(含别名) `/export/all_creators2`

**返回**: JSON，含 regular_name, aliases_all

**用途**: 获取作译者及其别名（如鸠摩罗什/童寿）

**示例返回**:
```json
{
  "regular_name": "鸠摩罗什",
  "aliases_all": ["童寿", "Kumārajīva"]
}
```

---

### 4. 朝代统计 `/export/dynasty`

**返回**: CSV格式字符串

**用途**: 获取各朝代佛典数量统计

---

### 5. 朝代-作品关联 `/export/dynasty_works`

**返回**: JSON，朝代与作品的关联数据

**用途**: 分析各朝代翻译/撰述情况

---

### 6. 检查清单 `/export/check_list`

**参数**: canon (如 J)

**返回**: CSV文件

**用途**: 导出某藏经的检查清单

---

## 服务器类 API

### 1. 健康检查 `/health`

**返回**: JSON状态信息

---

### 2. 统计报表 `/report/total`

**返回**:
- `works_all`: 总佛典数 (4868)
- `juans_all`: 总卷数 (21955)
- `cjk_chars_all`: 总字数

---

### 3. 数据变更 `/changes`

**参数**: work (可选)
**返回**: 数据变更历史

---

*文档生成时间: 2026-04-16*