# CBETA Skill 规划文档

## 一、Skill 定位

### 名称
`cbeta` - 中华电子佛典智能助手

### 描述（触发条件）
当用户：
- 引用佛经句子并询问出处
- 使用「出处」「来源」「CBETA引用」等关键词
- 查询佛经内容、经文原文
- 提供佛经片段要求确认来源
- 询问某句话出自哪部经典
- 需要标准学术引用格式
- 搜索佛教相关文本
- 使用「般若」「金刚」「法华」「阿含」等佛经关键词
- 提供经号（如 T0235、T0001）查询信息
- 需要简繁转换（佛经语境）

**必须触发此 skill**，即使用户没有明确说「CBETA」。

---

## 二、核心功能模块

### 1. 智能出处查找 (Source Finder)
**输入**: 用户提供的佛经句子（简体或繁体）
**输出**:
- 经典名称、经号
- 译者/作者信息
- 时代/年份
- 精确页码栏行号
- 标准 CBETA 引用格式

**流程**:
```
用户输入 → 简繁检测 → sc2tc转换 → API搜索 → 时间排序 →
识别经本（排除注疏） → goto获取起始行号 → lines获取全文 →
定位关键词（去标点匹配） → 解析linehead → 生成引用格式
```

**引用格式**:
```
《经名》：「引用文」(CBETA 版本, 册号, no. 经号, p. 页码栏行)
例: 《金刚般若波罗蜜经》：「应无所住而生其心」(CBETA 2025.R3, T08, no. 235, p. 749c22-23)
```

**经本识别规则**:
- 标题以「经」结尾
- 排除注疏作品（标题含註、疏、論、義、記、解、釋）
- 优先大正藏（T）
- 按time_from排序取最早

### 2. 智能搜索 (Smart Search)
**功能**:
- 自动检测简体/繁体输入
- 调用 sc2tc API 转换
- 尝试标准搜索，失败则尝试模糊搜索(fuzzy)
- 支持布尔搜索(extended)：AND/OR/NOT/NEAR

**搜索类型**:
| 类型 | API端点 | 适用场景 |
|------|---------|----------|
| 标准搜索 | `/search` | 一般全文检索 |
| 布尔搜索 | `/search/extended` | AND/OR/NOT组合 |
| 模糊搜索 | `/search/fuzzy` | 容错匹配 |
| 同义词搜索 | `/search/synonym` | 异体字扩展 |
| KWIC搜索 | `/kwic3` | 关键词上下文 |

**参数支持**:
- `--canon`: 藏经筛选 (T, X, K 等)
- `--category`: 部类筛选（般若部类、阿含部类等22类）
- `--dynasty`: 朝代筛选
- `--rows`: 返回数量
- `--order`: 排序（time_from+, time_to-, term_hits-）

### 3. 作品信息查询 (Work Info)
**API**: `/works?work={经号}`
**输出字段**:
| 字段 | 说明 |
|------|------|
| work | 佛典编号 |
| title | 佛典题名 |
| category | 所属部类 |
| byline | 作译者行 |
| creators | 作者/译者列表 |
| time_dynasty | 成立朝代 |
| time_from/time_to | 成立年代范围 |
| cjk_chars | 中日韩文字数 |
| juan | 卷数 |

### 4. 内容获取 (Content Fetcher)
**API组合**:
- `/juans/goto`: 获取卷起始行号
- `/lines`: 获取行内容

**Goto参数**:
| 参数 | 说明 |
|------|------|
| canon | 藏经代码 |
| work | 经号 |
| juan | 卷号 |
| linehead | 行首信息（如T08n0235_p0749c22） |

**Lines参数**:
| 参数 | 说明 |
|------|------|
| linehead | 单行行首 |
| linehead_start/end | 行范围 |
| before/after | 前后行数 |

### 5. 关键词定位 (Keyword Locator)
**特点**:
- 支持跨行匹配
- 支持去除标点匹配（处理「，」「。」「、」等）
- 解析linehead格式：`T08n0235_p0749c22`
  - T08: 册号
  - n0235: 经号
  - p0749: 页码
  - c22: 下栏(c)第22行
- 返回精确页码栏行号

### 6. 目录结构获取 (TOC)
**API**: `/works/toc?work={经号}`
**返回**: 树状目录结构，含children

### 7. 简繁转换 (SC2TC)
**API**: `/chinese_tools/sc2tc?q={简体文本}`
**特点**: 返回纯文本，非JSON

### 8. 分词服务 (Word Seg)
**API**: `/word_seg2?payload={文本}`
**用途**: 处理长句关键词拆分

---

## 三、API 接口完整映射

### 搜索类 (Search)
| 功能 | API Endpoint | 参数 |
|------|--------------|------|
| 全文搜索 | `/search` | q, rows, start, order, fields, canon, category, dynasty, work |
| 布尔搜索 | `/search/extended` | q(双引号), rows, start |
| 模糊搜索 | `/search/fuzzy` | q, rows |
| 同义词搜索 | `/search/synonym` | q, rows |
| 简体搜索 | `/search/sc` | q, rows |
| KWIC搜索 | `/kwic3` | q, work, juan, note, mark, sort, seg, place |
| 经目搜索 | `/search/toc` | q, rows |
| 标题搜索 | `/search/title` | q, rows |
| 注释搜索 | `/search/notes` | q, rows |
| 异体字搜索 | `/search/variants` | q |
| 相似文本 | `/search/similar` | work |
| 分面统计 | `/search/facet` | q, by(canon/category/dynasty) |

### 佛典类 (Work)
| 功能 | API Endpoint | 参数 |
|------|--------------|------|
| 佛典信息 | `/works` | work |
| 佛典目录 | `/works/toc` | work |
| 卷列表 | `/juans` | work |
| 卷定位 | `/juans/goto` | canon, work, juan, page, col, line, linehead |
| 字数统计 | `/works/word_count` | work |

### 行内容类 (Line)
| 功能 | API Endpoint | 参数 |
|------|--------------|------|
| 获取单行 | `/lines` | linehead, before, after |
| 获取行范围 | `/lines` | linehead_start, linehead_end |

### 目录类 (Catalog)
| 功能 | API Endpoint | 参数 |
|------|--------------|------|
| 目录条目 | `/catalog_entry` | entry |
| 部类查询 | `/category` | category |

### 工具类 (Tools)
| 功能 | API Endpoint | 参数 |
|------|--------------|------|
| 简繁转换 | `/chinese_tools/sc2tc` | q |
| 自动分词 | `/word_seg2` | payload |

### 导出类 (Export)
| 功能 | API Endpoint | 返回 |
|------|--------------|------|
| 全部佛典 | `/export/all_works` | JSON数组 |
| 全部作译者 | `/export/all_creators` | JSON |
| 作译者(含别名) | `/export/all_creators2` | JSON |
| 朝代统计 | `/export/dynasty` | CSV字符串 |
| 检查清单 | `/export/check_list` | CSV文件 |

### 服务器类 (Server)
| 功能 | API Endpoint | 返回 |
|------|--------------|------|
| 健康检查 | `/health` | JSON |
| 统计报表 | `/report/total` | JSON |
| 数据变更 | `/changes` | work |

### Base URL
`https://api.cbetaonline.cn`

### 版本信息
- API 版本: 3.6.9
- 资料版本: 2025.R3

---

## 四、Skill 结构

```
cbeta/
├── SKILL.md           # 主指令文件
├── scripts/
│   └── cbeta_api.py   # API 封装脚本（核心）
└── references/
    ├── api_endpoints.md  # API 接口完整文档
    ├── citation_format.md # 引用格式说明
    ├── canon_codes.md    # 藏经代码对照表
    ├── categories.md     # 22部类名称
    └── goto_codes.md     # 快速定位代码
```

---

## 五、使用场景示例

### 场景 1: 出处查找
```
用户: "应无所住而生其心出自哪里"
Skill:
1. 检测简体 → sc2tc转换为「應無所住而生其心」
2. search API 找到金刚经 T0235
3. 按time_from排序，识别经本（标题含「經」且不含注疏词）
4. goto获取卷1起始行号
5. lines获取全文
6. 去标点匹配定位关键词
7. 返回:
   【原始出处】金刚般若波罗蜜经 (T0235)
   【标准引用】《金刚般若波罗蜜经》：「应无所住而生其心」(CBETA 2025.R3, T08, no. 235, p. 749c22-23)
```

### 场景 2: 多版本对比
```
用户: "色即是空在哪些经文中出现"
Skill:
1. 搜索「色即是空」
2. 按time_from排序所有结果
3. 显示各版本出处列表
4. 标注主要出处（心经、大般若经等）
```

### 场景 3: 经文信息
```
用户: "查一下T0235金刚经的基本信息"
Skill:
1. 调用 works API
2. 显示经号、标题、译者、字数、卷数、时代
```

### 场景 4: 全文获取
```
用户: "帮我看看金刚经第一卷的内容"
Skill:
1. goto API 获取卷1起始行号
2. lines API 获取内容
3. 显示全文（或摘要）
```

### 场景 5: 布尔搜索
```
用户: "找同时包含'般若'和'金刚'的经文"
Skill:
1. 使用 extended API
2. q="般若" "金刚"
3. 返回交集结果
```

### 场景 6: NEAR搜索
```
用户: "找'老子'附近7字内有'道'的内容"
Skill:
1. 使用 kwic API
2. q='"老子" NEAR/7 "道"'
3. 返回上下文结果
```

### 场景 7: 部类筛选
```
用户: "在般若部类中搜索'空'"
Skill:
1. search API with category=般若部类
2. 返回该部类内结果
```

---

## 六、输出格式规范

### 出处查找输出模板
```markdown
## 出处查找结果

**关键词**: [用户输入]

### 原始出处
- **经典**: [经名] ([经号])
- **译者**: [译者信息]
- **时代**: [朝代] ([年份])
- **藏经**: [藏经代码] ([册号])

### 标准 CBETA 引用格式
《[经名]》：「[引用文]」(CBETA [版本], [册号], no. [经号], p. [页码栏行])

### 其他出处
[如有多个出处，按时间排序显示]
```

### 搜索结果输出模板
```markdown
## 搜索结果

**关键词**: [关键词]
**结果数**: [数量] 卷
**词频**: [总次数]

| 序号 | 经号 | 经名 | 词频 | 时代 | 部类 |
|------|------|------|------|------|------|
| 1 | T0235 | 金刚般若波罗蜜经 | 3 | 后秦 | 般若部类 |
...
```

### 佛典信息输出模板
```markdown
## 佛典信息

- **经号**: [经号]
- **经名**: [标题]
- **部类**: [category]
- **译者**: [byline]
- **时代**: [朝代] ([time_from]-[time_to])
- **卷数**: [juan]
- **字数**: [cjk_chars] 字
```

---

## 七、技术要点

### 1. 简繁转换
- 调用 CBETA API `/chinese_tools/sc2tc`
- 返回纯文本，非 JSON
- 自动检测：检查常用简体字（如「应」「无」「经」）

### 2. 经本识别
- 排除注疏作品：标题含註、疏、論、義、記、解、釋
- 优先选择大正藏（T）
- 识别标题以「经」结尾的作品
- 按time_from排序取最早

### 3. 页码获取流程
```
search → work, juan
goto(canonical_work, juan) → linehead_start
lines(linehead_start, linehead_end) → full_text
full_text.search(keyword) → position
parse_linehead → page, col, line
```

### 4. Linehead 格式解析
格式: `T08n0235_p0749c22`
- T08: 册号（T大正藏第8册）
- n0235: 经号（0235号）
- p0749: 页码（第749页）
- c22: 下栏(c)第22行

栏位代码:
- a = 上栏
- b = 中栏
- c = 下栏

### 5. 跨行匹配
- 合并所有行文本
- 去除标点匹配（删除「，」「。」「、」「；」「：」等）
- 计算关键词在合并文本中的位置
- 定位到具体行

### 6. 常用快速定位代码
| 代码 | 对应 | Linehead |
|------|------|----------|
| SA | 杂阿含 | T02n0099 |
| MA | 中阿含 | T01n0026 |
| DA | 长阿含 | T01n0001 |
| EA | 增壹阿含 | T02n0125 |
| SN | 相应部 | N13n0006 |
| MN | 中部 | N10n0003 |
| DN | 长部 | N09n0001 |
| AN | 增支部 | N12n0005 |

### 7. 藏经代码
| ID | 名称 | 佛典数 |
|----|------|--------|
| T | 大正藏 | 2,457 |
| X | 新纂卍续藏 | 1,230 |
| A | 宋—金藏 | 9 |
| K | 宋—高丽藏 | 9 |
| S | 宋—宋藏遗珍 | 2 |
| F | 房山石经 | 27 |
| C | 中国佛寺志 | 11 |
| D | 国图善本 | 64 |
| N | 南传大藏经 | 38 |
| J | 日本佛寺志 | 285 |
| ZW | 现代人著作 | 202 |

### 8. 22部类名称
```
本緣部類、阿含部類、般若部類、法華部類、華嚴部類
寶積部類、涅槃部類、大集部類、經集部類、密教部類
律部類、毘曇部類、中觀部類、瑜伽部類、論集部類
淨土宗部類、禪宗部類、史傳部類、事彙部類
敦煌寫本部類、國圖善本部類、南傳大藏經部類、新編部類
```

---

## 八、测试用例

### Test 1: 出处查找（简体）
**Prompt**: "应无所住而生其心出自哪里"
**期望**:
- 自动转换繁体
- 正确识别金刚经 T0235
- 返回精确页码 749c22-23
- 生成标准引用格式

### Test 2: 出处查找（无标点）
**Prompt**: "一切有为法如梦幻泡影出自哪部经"
**期望**:
- 去标点匹配
- 正确定位金刚经结尾偈
- 显示页码

### Test 3: 多版本出处
**Prompt**: "色即是空在哪些经文里出现"
**期望**:
- 返回多个版本
- 按时间排序
- 显示主要出处（心经、大般若经）

### Test 4: 经文信息
**Prompt**: "帮我查一下T0262法华经的基本信息"
**期望**:
- 返回经号、标题、译者
- 显示时代、字数、卷数

### Test 5: 布尔搜索
**Prompt**: "找同时提到'舍利弗'和'须菩提'的经文"
**期望**:
- 使用extended API
- 返回交集结果

### Test 6: 部类筛选
**Prompt**: "在般若部类中搜索'智慧'"
**期望**:
- 指定category=般若部类
- 返回该部类内结果

---

## 九、CLI 命令映射

### 已实现的CLI命令（56个，覆盖率100%）

| 命令组 | 命令 | Skill调用 |
|--------|------|-----------|
| search | query | smart_search() |
| search | kwic | search_kwic() |
| search | extended | search_extended() |
| search | fuzzy | search_fuzzy() |
| search | synonym | search_synonym() |
| search | sc | search_sc() |
| search | source | find_source() |
| search | toc | search_toc() |
| search | title | search_title() |
| search | notes | search_notes() |
| search | variants | search_variants() |
| search | similar | search_similar() |
| search | facet | search_facet() |
| work | info | works() |
| work | toc | work_toc() |
| work | content | work_content() |
| work | list | works() |
| work | wordcount | work_word_count() |
| work | download | download_info() |
| line | get | lines() |
| line | range | lines_range() |
| juan | list | juans() |
| juan | goto | juan_goto() |
| catalog | entry | catalog_entry() |
| catalog | category | category() |
| tools | sc2tc | sc2tc() |
| tools | wordseg | word_seg() |
| server | health | health() |
| server | stats | report_total() |
| server | changes | changes() |
| export | works | export_all_works() |
| export | creators | export_all_creators() |
| export | creators2 | export_all_creators2() |
| export | dynasty | export_dynasty() |
| export | check-list | export_check_list() |

---

## 十、预期效果

### 量化指标
- 出处查找准确率: >90%
- 页码定位准确率: >85%
- 简繁转换成功率: >95%
- 引用格式规范性: 100%

### 用户体验
- 一句话输入即可获得完整引用
- 无需了解 CBETA API 技术
- 自动处理简繁体差异
- 自动排除注疏、定位原典
- 支持布尔/模糊/同义词等高级搜索
- 支持部类/藏经/朝代筛选

---

## 十一、下一步实现

1. ✅ PLAN.md 规划文档完成
2. ⏳ 编写 SKILL.md 主文件
3. ⏳ 编写 scripts/cbeta_api.py 封装脚本
4. ⏳ 编写 references 参考文档
5. ⏳ 创建测试用例
6. ⏳ 运行评测迭代

---

*文档更新时间: 2026-04-16*