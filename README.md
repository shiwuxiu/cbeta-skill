# CBETA 中华电子佛典智能助手

> 中华电子佛典协会（CBETA）API 的完整封装，支持智能出处查找、批量并发搜索、精确页码定位。

## 核心功能

| 功能 | 描述 |
|------|------|
| 智能出处查找 | 输入佛经句子，自动生成标准 CBETA 引用格式 |
| 精确页码定位 | 搜索结果无 `lb` 时自动调用 KWIC 补全页码（100% 覆盖） |
| 异步并发批量 | 并发查询多个关键词，2.8x 加速 |
| 配置文件系统 | 支持 JSON/YAML 配置持久化 |

## 安装

```bash
# 克隆仓库
git clone https://github.com/shiwuxiu/cbeta-skill.git

# 安装依赖
pip install requests aiohttp
```

## 快速使用

### 出处查找（最常用）

```python
from scripts.cbeta_api import CbetaAPI

api = CbetaAPI()
result = api.find_source("应无所住而生其心")

# 输出: 《金刚般若波罗蜜经》：「应无所住而生其心」(CBETA 2025.R3, T08, no. 235, p. 749c22-23)
print(result.get("citation"))
```

### 批量出处查找

```python
# 并发批量查找
results = api.batch_find_sources_concurrent(
    ["应无所住", "色即是空", "一切有为法"],
    max_concurrent=5
)
```

### CLI 工具

```bash
# 出处查找
python -m cli_anything.cbeta search source "应无所住而生其心"

# 批量查找
python -m cli_anything.cbeta search batch "应无所住" "色即是空" -c 5

# JSON 输出
python -m cli_anything.cbeta search batch "关键词1" "关键词2" -j

# 汇总模式
python -m cli_anything.cbeta search batch "关键词1" "关键词2" --summary
```

## API 端点

| 功能 | 端点 | 状态 |
|------|------|------|
| 全文搜索 | `/search` | ✅ |
| 布尔搜索 | `/search/extended` | ✅ |
| KWIC搜索 | `/search/kwic` | ✅ |
| 佛典信息 | `/works` | ✅ |
| 简繁转换 | `/chinese_tools/sc2tc` | ✅ |
| 导出佛典 | `/export/all_works` | ✅ |

## 引用格式规范

```
《经名》：「引用文」(CBETA 版本, 册号, no. 经号, p. 页码栏行)

例: 《金刚般若波罗蜜经》：「应无所住而生其心」(CBETA 2025.R3, T08, no. 235, p. 749c22-23)
```

### 页码格式说明

| 格式 | 说明 |
|------|------|
| `p. 749c22` | 单行 |
| `p. 749c22-23` | 跨行 |
| `p. 749c22-b05` | 跨栏 |
| `pp. 749c22-750a05` | 跨页 |

栏位：a=上栏, b=中栏, c=下栏

## 配置系统

```python
from scripts.cbeta_api import CbetaAPI, CbetaConfig

# 从文件加载配置
config = CbetaConfig.load("config.json")
api = CbetaAPI(config=config)

# 保存配置到文件
config.save("config.yaml")
```

**默认配置**：
| 参数 | 默认值 | 说明 |
|------|------|------|
| `cache_expire_seconds` | 3600 | 缓存有效期 |
| `timeout` | 30 | 请求超时秒数 |
| `max_retries` | 3 | 最大重试次数 |
| `rate_limit` | 10 | 每秒请求限制 |
| `max_concurrent` | 5 | 最大并发数 |

## 项目结构

```
cbeta-skill/
├── SKILL.md              # Skill 文档（Claude Code 使用）
├── PLAN.md               # 开发规划
├── README.md             # 本文件
├── .gitignore
├── scripts/
│   ├── cbeta_api.py      # API 核心代码
│   └── tests/
│       └── test_cbeta_api.py  # 单元测试
└── references/
    ├── api_endpoints.md  # API 端点文档
    ├── citation_format.md # 引用格式详解
    └── canon_codes.md    # 藏经代码对照表
```

## 运行测试

```bash
cd scripts
python -m pytest tests/test_cbeta_api.py -v
```

## 数据来源

本项目使用中华电子佛典协会（CBETA）提供的开放 API。

- **API 文档**: https://cbdata.dila.edu.tw/stable/
- **API 版本**: 3.6.9
- **资料版本**: 2025.R3
- **佛典数量**: 4,868 部
- **总卷数**: 21,955 卷

## 许可证

MIT License

## 致谢

感谢中华电子佛典协会（CBETA）提供的高质量佛典数字化资源。

---

*CBETA 中华电子佛典智能助手 v2.0*