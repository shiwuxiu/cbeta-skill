"""
CBETA API 封装脚本

提供中华电子佛典协会 API 的完整功能封装：
- 智能出处查找 + 标准引用格式生成
- KWIC 关键词上下文搜索
- 简繁转换
- 缓存机制（内存缓存）
- 重试机制（递增延迟）
- Rate Limiter（请求速率控制）
- 导出方法
- 备选 URL 自动切换

API 版本: 3.6.9
资料版本: 2025.R3

备选 Base URL（按优先级）：
1. https://cbdata.dila.edu.tw/stable/  (官方新端点)
2. https://api.cbetaonline.cn          (旧端点，部分网络可用)
"""

import re
import os
import json
import copy
import time
import threading
import hashlib
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Any
import requests
import aiohttp
from requests.packages.urllib3.exceptions import InsecureRequestWarning
# 跳过 SSL 警告（CBETA 服务器证书配置问题）
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
from typing import Optional, Dict, List, Tuple, Any
from urllib.parse import urlencode

# 备选 URL 配置（按优先级排序）
BASE_URLS = [
    {"url": "https://cbdata.dila.edu.tw", "prefix": "/stable", "name": "官方新端点"},
    {"url": "https://api.cbetaonline.cn", "prefix": "", "name": "旧端点"},
]

# 默认使用第一个
BASE_URL = BASE_URLS[0]["url"]
API_PREFIX = BASE_URLS[0]["prefix"]
CBETA_VERSION = "2025.R3"
TIMEOUT = 30

# 简体字检测集合
SIMPLIFIED_CHARS = set('应无经这那说从学时过对会来去开把与义据提处起间国文断新')

# 排除注疏的关键词
COMMENTARY_WORDS = ['註', '疏', '論', '義', '記', '解', '釋', '注', '钞', '科']

# 常见经文页码映射表（用于快速定位，减少 goto API 调用）
# 格式：work -> (起始页, 结束页, 册号)
COMMON_WORK_PAGES = {
    # 金刚经相关
    "T0235": (748, 752, "T08"),  # 金刚般若波罗蜜经（鸠摩罗什译）
    "T0236a": (752, 755, "T08"),  # 金刚般若波罗蜜经（留支译）
    "T0236b": (755, 758, "T08"),
    "T0237": (762, 767, "T08"),  # 金刚般若波罗蜜经（真谛译）
    "T0238": (767, 769, "T08"),  # 金刚能断般若波罗蜜经
    "T0239": (770, 776, "T08"),  # 佛说能断金刚般若波罗蜜多经

    # 心经相关
    "T0250": (848, 849, "T08"),  # 般若波罗蜜多心经（玄奘译）
    "T0251": (849, 850, "T08"),  # 摩诃般若波罗蜜大明咒经

    # 阿含经
    "T0001": (1, 70, "T01"),     # 长阿含经
    "T0002": (1, 158, "T01"),    # 中阿含经
    "T0099": (1, 156, "T02"),    # 杂阿含经
    "T0125": (1, 108, "T02"),    # 增壹阿含经

    # 法华经
    "T0262": (1, 62, "T09"),     # 妙法莲华经

    # 华严经
    "T0278": (1, 446, "T09"),    # 大方广佛华严经（六十华严）
    "T0279": (1, 408, "T10"),    # 大方广佛华严经（八十华严）

    # 涅槃经
    "T0374": (1, 612, "T12"),    # 大般涅槃经

    # 维摩诘经
    "T0474": (1, 45, "T14"),     # 维摩诘所说经

    # 阿弥陀经
    "T0366": (1, 4, "T12"),      # 佛说阿弥陀经

    # 地藏经
    "T0412": (1, 15, "T13"),     # 地藏菩萨本愿经

    # 无量寿经
    "T0360": (1, 12, "T12"),     # 佛说无量寿经

    # 圆觉经
    "T0480": (1, 16, "T17"),     # 圆觉经

    # 楞严经
    "T0945": (1, 142, "T19"),    # 大佛顶首楞严经
}


# ── 配置管理 ────────────────────────────────────────────────

class CbetaConfig:
    """CBETA API 配置类 - 支持自定义各项参数."""

    DEFAULT_CONFIG = {
        "cache_dir": None,           # 缓存目录（默认 ~/.cache/cbeta）
        "cache_expire_seconds": 3600, # 缓存有效期（秒）
        "timeout": 30,               # 请求超时时间（秒）
        "max_retries": 3,            # 最大重试次数
        "retry_delay": 1.0,          # 重试延迟基数（秒）
        "rate_limit": 10,            # 每秒请求限制
        "max_concurrent": 5,         # 并发最大数
        "default_rows": 20,          # 默认搜索结果数
    }

    def __init__(self, config_file: Optional[str] = None, **kwargs):
        """初始化配置.

        Args:
            config_file: 配置文件路径（JSON 或 YAML）
            **kwargs: 直接指定的配置参数
        """
        self._config = copy.deepcopy(self.DEFAULT_CONFIG)

        # 从配置文件加载
        if config_file:
            self._load_from_file(config_file)

        # 应用直接指定的参数
        for key, value in kwargs.items():
            if key in self._config:
                self._config[key] = value

        # 设置默认缓存目录
        if self._config["cache_dir"] is None:
            self._config["cache_dir"] = os.path.join(
                os.path.expanduser("~"), ".cache", "cbeta"
            )

    def _load_from_file(self, config_file: str):
        """从配置文件加载配置."""
        try:
            path = Path(config_file)
            if not path.exists():
                return

            with open(path, 'r', encoding='utf-8') as f:
                if path.suffix in ['.yaml', '.yml']:
                    import yaml
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)

            # 合并配置
            if data:
                for key, value in data.items():
                    if key in self._config:
                        self._config[key] = value
        except Exception:
            pass  # 配置加载失败，使用默认值

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        """设置配置值."""
        if key in self._config:
            self._config[key] = value

    @property
    def cache_dir(self) -> str:
        return self._config["cache_dir"]

    @property
    def timeout(self) -> int:
        return self._config["timeout"]

    @property
    def max_retries(self) -> int:
        return self._config["max_retries"]

    @property
    def max_concurrent(self) -> int:
        return self._config["max_concurrent"]

    def to_dict(self) -> Dict:
        """导出配置为字典."""
        return copy.deepcopy(self._config)

    def save(self, config_file: str):
        """保存配置到文件."""
        path = Path(config_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            if path.suffix in ['.yaml', '.yml']:
                import yaml
                yaml.dump(self._config, f, default_flow_style=False)
            else:
                json.dump(self._config, f, indent=2)


# 全局默认配置
_default_config: Optional[CbetaConfig] = None


def get_config() -> CbetaConfig:
    """获取全局配置实例."""
    global _default_config
    if _default_config is None:
        config_file = os.path.join(
            os.path.expanduser("~"), ".cbeta", "config.json"
        )
        _default_config = CbetaConfig(config_file)
    return _default_config


def set_config(config: CbetaConfig):
    """设置全局配置."""
    global _default_config
    _default_config = config


class RateLimiter:
    """请求速率限制器 - 防止请求过快触发 API 限制."""

    def __init__(self, requests_per_second: int = 10):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self.lock = threading.Lock()

    def wait(self):
        """等待直到可以发送下一个请求."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()


class SimpleCache:
    """简易内存缓存 - 减少重复请求."""

    def __init__(self, expire_seconds: int = 3600):
        self._cache: Dict[str, Dict] = {}
        self._expire_seconds = expire_seconds

    def _generate_key(self, endpoint: str, params: Optional[Dict]) -> str:
        """生成缓存键."""
        param_str = urlencode(params or {})
        return hashlib.md5(f"{endpoint}:{param_str}".encode()).hexdigest()

    def get(self, endpoint: str, params: Optional[Dict]) -> Optional[Any]:
        """获取缓存."""
        key = self._generate_key(endpoint, params)
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry['timestamp'] < self._expire_seconds:
                return entry['data']
            del self._cache[key]
        return None

    def set(self, endpoint: str, params: Optional[Dict], data: Any):
        """设置缓存."""
        key = self._generate_key(endpoint, params)
        self._cache[key] = {'data': data, 'timestamp': time.time()}

    def clear(self):
        """清空缓存."""
        self._cache.clear()

    def stats(self) -> Dict:
        """缓存统计."""
        return {
            'entries': len(self._cache),
            'expire_seconds': self._expire_seconds
        }


class FileCache:
    """持久化文件缓存 - 重启后缓存保留.

    缓存存储在 ~/.cache/cbeta/ 目录下，使用 JSON 文件保存。
    """

    def __init__(self, expire_seconds: int = 3600, cache_dir: str = None):
        self._expire_seconds = expire_seconds
        # 默认缓存目录
        if cache_dir is None:
            home = os.path.expanduser("~")
            self._cache_dir = os.path.join(home, ".cache", "cbeta")
        else:
            self._cache_dir = cache_dir

        # 确保目录存在
        os.makedirs(self._cache_dir, exist_ok=True)

        # 内存缓存（用于快速访问）
        self._memory_cache: Dict[str, Dict] = {}

        # 启动时清理过期缓存
        self._cleanup_expired()

    def _generate_key(self, endpoint: str, params: Optional[Dict]) -> str:
        """生成缓存键."""
        param_str = urlencode(params or {})
        return hashlib.md5(f"{endpoint}:{param_str}".encode()).hexdigest()

    def _get_cache_file(self, key: str) -> str:
        """获取缓存文件路径."""
        return os.path.join(self._cache_dir, f"{key}.json")

    def get(self, endpoint: str, params: Optional[Dict]) -> Optional[Any]:
        """获取缓存（先查内存，再查文件）."""
        key = self._generate_key(endpoint, params)
        now = time.time()

        # 1. 先查内存缓存
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if now - entry['timestamp'] < self._expire_seconds:
                return entry['data']
            del self._memory_cache[key]

        # 2. 查文件缓存
        cache_file = self._get_cache_file(key)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    entry = json.load(f)
                if now - entry['timestamp'] < self._expire_seconds:
                    # 加载到内存缓存
                    self._memory_cache[key] = entry
                    return entry['data']
                else:
                    # 过期，删除文件
                    os.remove(cache_file)
            except (json.JSONDecodeError, IOError):
                # 文件损坏，删除
                try:
                    os.remove(cache_file)
                except:
                    pass

        return None

    def set(self, endpoint: str, params: Optional[Dict], data: Any):
        """设置缓存（同时写入内存和文件）."""
        key = self._generate_key(endpoint, params)
        entry = {'data': data, 'timestamp': time.time()}

        # 1. 写入内存
        self._memory_cache[key] = entry

        # 2. 写入文件
        cache_file = self._get_cache_file(key)
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(entry, f, ensure_ascii=False)
        except IOError:
            pass  # 文件写入失败不影响使用

    def clear(self):
        """清空缓存（内存+文件）."""
        # 清空内存
        self._memory_cache.clear()

        # 清空文件
        for filename in os.listdir(self._cache_dir):
            if filename.endswith('.json'):
                try:
                    os.remove(os.path.join(self._cache_dir, filename))
                except:
                    pass

    def _cleanup_expired(self):
        """清理过期的缓存文件."""
        now = time.time()
        for filename in os.listdir(self._cache_dir):
            if filename.endswith('.json'):
                cache_file = os.path.join(self._cache_dir, filename)
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        entry = json.load(f)
                    if now - entry['timestamp'] >= self._expire_seconds:
                        os.remove(cache_file)
                except:
                    pass

    def stats(self) -> Dict:
        """缓存统计."""
        # 统计文件缓存数量
        file_count = 0
        if os.path.exists(self._cache_dir):
            file_count = len([f for f in os.listdir(self._cache_dir) if f.endswith('.json')])

        return {
            'memory_entries': len(self._memory_cache),
            'file_entries': file_count,
            'cache_dir': self._cache_dir,
            'expire_seconds': self._expire_seconds
        }


class CbetaAPI:
    """CBETA API 封装类，支持备选 URL 自动切换."""

    def __init__(self, timeout: int = 30, max_retries: int = 3,
                 retry_delay: float = 1.0, rate_limit: int = 10,
                 cache_expire: int = 3600, use_file_cache: bool = True):
        self.base_urls = BASE_URLS
        self.current_url_index = 0  # 当前使用的 URL 索引
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self.session.headers.update({
            "Referer": "cbeta-skill",
            "Accept": "application/json",
            "User-Agent": "cbeta-skill/1.0"
        })

        # Rate Limiter
        self._rate_limiter = RateLimiter(rate_limit)

        # 缓存（默认使用文件缓存，重启后保留）
        if use_file_cache:
            self._cache = FileCache(cache_expire)
        else:
            self._cache = SimpleCache(cache_expire)

    def _get_current_url_config(self) -> Dict:
        """获取当前 URL 配置."""
        return self.base_urls[self.current_url_index]

    def _switch_to_next_url(self) -> bool:
        """切换到下一个备选 URL."""
        if self.current_url_index < len(self.base_urls) - 1:
            self.current_url_index += 1
            config = self._get_current_url_config()
            print(f"[CBETA] 切换到备选 URL: {config['name']} ({config['url']})")
            return True
        return False  # 已尝试所有 URL

    def _request(self, endpoint: str, params: Optional[Dict] = None,
                 use_cache: bool = True, is_text: bool = False) -> Any:
        """发送 API 请求（带缓存、重试、Rate Limiter、备选 URL 切换）.

        Args:
            endpoint: API 端点
            params: 请求参数
            use_cache: 是否使用缓存
            is_text: 是否返回纯文本（用于 sc2tc）
        """
        # 检查缓存
        if use_cache and not is_text:
            cached = self._cache.get(endpoint, params)
            if cached is not None:
                return cached

        # 尝试所有备选 URL
        url_index_start = self.current_url_index
        for url_attempt in range(len(self.base_urls)):
            config = self.base_urls[self.current_url_index]
            url = f"{config['url']}{config['prefix']}{endpoint}"

            # Rate limiting
            self._rate_limiter.wait()

            # 重试机制
            for attempt in range(self.max_retries):
                try:
                    response = self.session.get(url, params=params, timeout=self.timeout, verify=False)
                    response.raise_for_status()

                    if is_text:
                        result = response.text.strip()
                    else:
                        result = response.json()

                    # 写入缓存
                    if use_cache and not is_text:
                        self._cache.set(endpoint, params, result)

                    return result

                except requests.exceptions.RequestException as e:
                    if attempt < self.max_retries - 1:
                        # 递增延迟
                        time.sleep(self.retry_delay * (attempt + 1))
                    else:
                        # 当前 URL 所有重试失败，尝试下一个 URL
                        if self._switch_to_next_url():
                            break  # 跳出重试循环，进入下一个 URL
                        else:
                            # 所有 URL 都失败了
                            raise RuntimeError(f"API request failed after trying all URLs: {e}")

    def is_simplified(self, text: str) -> bool:
        """检测文本是否为简体中文."""
        return any(char in SIMPLIFIED_CHARS for char in text)

    def sc2tc(self, text: str) -> str:
        """简体转繁体."""
        return self._request("/chinese_tools/sc2tc", {"q": text}, use_cache=False, is_text=True)

    # ── 搜索方法 ──────────────────────────────────────────────────────

    def search(self, q: str, rows: int = 20, order: str = "time_from+",
               canon: str = None, category: str = None, dynasty: str = None,
               work: str = None, creator: str = None) -> Dict:
        """全文搜索."""
        params = {"q": q, "rows": rows, "order": order}
        if canon:
            params["canon"] = canon
        if category:
            params["category"] = category
        if dynasty:
            params["dynasty"] = dynasty
        if work:
            params["work"] = work
        if creator:
            params["creator"] = creator
        return self._request("/search", params)

    def search_extended(self, q: str, rows: int = 20) -> Dict:
        """布尔搜索（AND/OR/NOT）."""
        return self._request("/search/extended", {"q": q, "rows": rows})

    def search_fuzzy(self, q: str, rows: int = 20) -> Dict:
        """模糊搜索 - 注意：此端点在新API中不可用.

        建议使用 search() 或 smart_search() 替代.
        """
        return {"num_found": 0, "results": [], "error": "fuzzy endpoint not available in new API"}

    def search_synonym(self, q: str, rows: int = 20) -> Dict:
        """同义词搜索."""
        return self._request("/search/synonym", {"q": q, "rows": rows})

    def search_title(self, q: str, rows: int = 20) -> Dict:
        """按标题搜索."""
        return self._request("/search/title", {"q": q, "rows": rows})

    def search_notes(self, q: str, rows: int = 20) -> Dict:
        """搜索注释/夹注."""
        return self._request("/search/notes", {"q": q, "rows": rows})

    def search_variants(self, q: str) -> Dict:
        """异体字搜索."""
        return self._request("/search/variants", {"q": q})

    def search_facet(self, q: str = None, facet_by: str = "canon") -> Dict:
        """分面统计."""
        params = {"facet_by": facet_by}
        if q:
            params["q"] = q
        return self._request("/search/facet", params)

    # ── KWIC 搜索 ──────────────────────────────────────────────────────

    def search_kwic(self, q: str, work: str = None, juan: int = None,
                    around: int = 10, mark: bool = False, note: bool = True) -> Dict:
        """KWIC 搜索 - 关键词上下文.

        Args:
            q: 搜索关键词
            work: 佛典编号（可选）
            juan: 卷号（可选）
            around: 上下文行数（实际参数无效，API 不支持）
            mark: 是否标记关键词（传 mark=1）
            note: 是否包含夹注（传 note=1）
        """
        params = {"q": q}
        if work:
            params["work"] = work
        if juan:
            params["juan"] = juan
        if mark:
            params["mark"] = 1
        else:
            params["mark"] = 0
        if note:
            params["note"] = 1
        else:
            params["note"] = 0
        return self._request("/search/kwic", params)

    def kwic_juan(self, q: str, work: str, juan: int, mark: bool = True, note: bool = True) -> Dict:
        """指定 work/juan 的 KWIC 搜索（支持 NEAR 语法）.

        NEAR 示例: '"老子" NEAR/7 "道"'
        """
        return self._request("/search/kwic", {
            "q": q, "work": work, "juan": juan,
            "mark": 1 if mark else 0,
            "note": 1 if note else 0
        })

    def kwic_extended(self, q: str, work: str = None) -> Dict:
        """扩展 KWIC - 返回所有关键词命中."""
        params = {"q": q}
        if work:
            params["work"] = work
        return self._request("/kwic/extended", params)

    # ── 佛典方法 ──────────────────────────────────────────────────────

    def get_work_info(self, work: str) -> Optional[Dict]:
        """获取佛典信息."""
        result = self._request("/works", {"work": work})
        if result and result.get("num_found", 0) > 0:
            return result["results"][0]
        return None

    def works(self, **kwargs) -> Dict:
        """搜索佛典（支持多种筛选条件）."""
        return self._request("/works", kwargs)

    def work_toc(self, work: str) -> Dict:
        """获取佛典目录结构."""
        return self._request("/works/toc", {"work": work})

    def work_word_count(self, work: str = None) -> Dict:
        """字数统计."""
        params = {}
        if work:
            params["work"] = work
        return self._request("/works/word_count", params)

    # ── 行内容方法 ──────────────────────────────────────────────────────

    def get_juan_start(self, canon: str, work: str, juan: int = 1) -> Optional[str]:
        """获取卷起始行号."""
        result = self._request("/juans/goto", {
            "canon": canon,
            "work": work.replace(canon, "").lstrip("0"),
            "juan": juan
        })
        if result.get("results"):
            return result["results"][0].get("linehead", "")
        return None

    def get_lines(self, linehead: str = None, linehead_start: str = None,
                  linehead_end: str = None, before: int = 0, after: int = 0) -> List[Dict]:
        """获取行内容."""
        params = {}
        if linehead:
            params["linehead"] = linehead
        if linehead_start:
            params["linehead_start"] = linehead_start
        if linehead_end:
            params["linehead_end"] = linehead_end
        if before > 0:
            params["before"] = before
        if after > 0:
            params["after"] = after
        result = self._request("/lines", params)
        return result.get("results", [])

    def juans(self, work: str) -> Dict:
        """获取佛典卷列表."""
        return self._request("/juans", {"work": work})

    # ── 目录方法 ──────────────────────────────────────────────────────

    def catalog_entry(self, entry: str) -> Dict:
        """获取目录条目."""
        return self._request("/catalog_entry", {"entry": entry})

    def category(self, category_name: str) -> Dict:
        """按部类查询."""
        return self._request(f"/category/{category_name}")

    # ── 工具方法 ──────────────────────────────────────────────────────

    def word_seg(self, text: str) -> Dict:
        """中文分词."""
        return self._request("/word_seg2", {"payload": text})

    # ── 导出方法 ──────────────────────────────────────────────────────

    def export_all_works(self) -> List[Dict]:
        """导出全部佛典列表（4868部）."""
        return self._request("/export/all_works")

    def export_all_creators(self) -> Dict:
        """导出全部作译者."""
        return self._request("/export/all_creators")

    def export_all_creators2(self) -> Dict:
        """导出作译者（含别名）."""
        return self._request("/export/all_creators2")

    def export_dynasty(self) -> Dict:
        """导出朝代信息."""
        return self._request("/export/dynasty")

    def export_dynasty_works(self) -> Dict:
        """导出朝代-作品关联."""
        return self._request("/export/dynasty_works")

    def export_check_list(self, canon: str = "J") -> Dict:
        """导出检查清单 CSV."""
        return self._request("/export/check_list", {"canon": canon})

    # ── 服务器方法 ──────────────────────────────────────────────────────

    def health(self) -> Dict:
        """健康检查."""
        # health 端点返回纯文本 "success"，需要特殊处理
        result = self._request("/health", is_text=True)
        if result == "success":
            return {"status": "OK"}
        return {"status": result}

    def report_total(self) -> Dict:
        """统计报表."""
        return self._request("/report/total")

    # ── 辅助方法 ──────────────────────────────────────────────────────

    def parse_linehead(self, linehead: str) -> Optional[Dict]:
        """解析行首信息.

        格式: T08n0235_p0749c22
        返回: {canon, vol, work, page, col, line}
        """
        match = re.match(r'([A-Z])(\d+)n(\d+)_p(\d+)([abc])(\d+)', linehead)
        if match:
            return {
                "canon": match.group(1),
                "vol": match.group(2),
                "work": match.group(3),
                "page": match.group(4),
                "col": match.group(5),
                "line": match.group(6)
            }
        return None

    def is_sutra(self, title: str) -> bool:
        """判断是否为经本（非注疏）."""
        # 标题以「经」结尾
        if not title.endswith('經') and not title.endswith('经'):
            return False
        # 排除注疏
        for word in COMMENTARY_WORDS:
            if word in title:
                return False
        return True

    def find_keyword_in_text(self, text: str, keyword: str) -> Optional[Tuple[int, int, str]]:
        """在文本中查找关键词（支持去标点匹配）.

        Returns: (原文起始位置, 原文结束位置, 匹配模式: "exact"/"no_punctuation")
        """
        # 先尝试精确匹配
        if keyword in text:
            idx = text.find(keyword)
            return (idx, idx + len(keyword), "exact")

        # 去标点匹配
        punct_pattern = r'[，。；：！？、　「」『』（）\s]'
        text_no_punc = re.sub(punct_pattern, '', text)
        keyword_no_punc = re.sub(punct_pattern, '', keyword)

        if keyword_no_punc in text_no_punc:
            idx_no_punc = text_no_punc.find(keyword_no_punc)

            # 计算原文中的对应位置
            punct_offset = 0
            orig_idx = 0
            for i, char in enumerate(text):
                if not re.match(punct_pattern, char):
                    if i - punct_offset == idx_no_punc:
                        orig_idx = i
                        break
                else:
                    punct_offset += 1

            # 计算结束位置
            end_punct_offset = 0
            orig_end = orig_idx
            text_from_start = text[orig_idx:]
            for i, char in enumerate(text_from_start):
                if not re.match(punct_pattern, char):
                    if i - end_punct_offset >= len(keyword_no_punc):
                        orig_end = orig_idx + i
                        break
                else:
                    end_punct_offset += 1

            return (orig_idx, orig_end, "no_punctuation")

        return None

    # ── 智能搜索 ──────────────────────────────────────────────────────

    def smart_search(self, q: str, rows: int = 20, **kwargs) -> Tuple[Dict, Dict]:
        """智能搜索 - 自动检测简/繁体，自动选择最佳搜索模式.

        Returns: (搜索结果, 搜索信息)
        """
        search_info = {
            "original_query": q,
            "converted_query": q,
            "effective_query": q,
            "is_simplified": False,
            "search_type": "standard"
        }

        # 检测简体，调用 API 精确转换
        if self.is_simplified(q):
            search_info["is_simplified"] = True
            tc_q = self.sc2tc(q)
            search_info["converted_query"] = tc_q
            search_info["effective_query"] = tc_q
            q = tc_q

        # 尝试标准搜索（按时间升序）
        result = self.search(q, rows=rows, order="time_from+", **kwargs)

        search_info["num_found"] = result.get("num_found", 0)
        search_info["total_hits"] = result.get("total_term_hits", 0)

        # 如果无结果，尝试模糊搜索
        if result.get("num_found") == 0:
            search_info["search_type"] = "fuzzy"
            result = self.search_fuzzy(q, rows=rows)
            search_info["num_found"] = result.get("num_found", 0)

        result["search_info"] = search_info
        return result, search_info

    # ── 出处查找 ──────────────────────────────────────────────────────

    def find_source(self, keyword: str, rows: int = 20) -> Dict:
        """出处查找 - 输入关键词，返回标准 CBETA 引用格式.

        Returns:
        {
            "keyword": 原始关键词,
            "work": 经号,
            "title": 经名,
            "byline": 译者,
            "time_dynasty": 朝代,
            "citation": 标准引用格式,
            "page": 页码信息
        }
        """
        # 智能搜索
        result, search_info = self.smart_search(keyword, rows=rows)

        if result.get("num_found") == 0:
            return {"error": "未找到相关内容", "keyword": keyword}

        # 筛选经本（排除注疏）
        sutra_results = []
        for item in result.get("results", []):
            title = item.get("title", "")
            if self.is_sutra(title):
                sutra_results.append(item)

        if not sutra_results:
            # 如果没有找到经本，返回第一个结果
            sutra_results = result.get("results", [])[:1]

        if not sutra_results:
            return {"error": "未找到经本内容", "keyword": keyword}

        # 取第一个结果作为主要出处
        first = sutra_results[0]
        work = first.get("work", "")
        title = first.get("title", "")
        byline = first.get("byline", "")
        time_dynasty = first.get("time_dynasty", "")
        juan = first.get("juan", 1)
        lb = first.get("lb", "")

        # 获取经号详细信息
        work_info = self.get_work_info(work)
        vol = ""
        if work_info:
            title = work_info.get("title", title)
            byline = work_info.get("byline", byline)
            time_dynasty = work_info.get("time_dynasty", time_dynasty)
            vol = work_info.get("vol", "")  # T08 格式
            file = work_info.get("file", "")  # T08n0235 格式

        # 如果搜索结果没有 lb，调用 KWIC 获取精确页码
        if not lb:
            # 转换关键词为繁体
            tc_keyword = self.sc2tc(keyword)
            kwic_result = self.search_kwic(tc_keyword, work=work, juan=juan)
            if kwic_result.get("num_found") > 0:
                kwic_first = kwic_result.get("results", [])[0]
                lb = kwic_first.get("lb", "")

        # 解析页码信息
        page_info = self._parse_linehead(lb) if lb else None

        # 生成标准引用格式
        citation = self._format_citation(
            title=title,
            keyword=keyword,
            work=work,
            vol=vol,
            lb=lb,
            version="2025.R3"
        )

        return {
            "keyword": keyword,
            "work": work,
            "title": title,
            "byline": byline,
            "time_dynasty": time_dynasty,
            "citation": citation,
            "page": page_info,
            "lb": lb
        }

    def _parse_linehead(self, linehead: str) -> Dict:
        """解析行首信息（T08n0235_p0749c22 -> 册、经、页、栏、行）."""
        if not linehead:
            return None

        try:
            # 格式: T08n0235_p0749c22 或 0749c22
            if "_" in linehead:
                parts = linehead.split("_")
                prefix = parts[0]  # T08n0235
                page_part = parts[1] if len(parts) > 1 else ""  # 0749c22

                # 解析册号和经号
                canon = prefix[0]  # T
                vol_match = re.search(r'\d+', prefix[1:4])  # 08
                vol = vol_match.group() if vol_match else ""
                work_match = re.search(r'n(\d+)', prefix)  # n0235
                work_num = work_match.group(1) if work_match else ""
            else:
                # 简化格式 0749c22
                page_part = linehead
                canon = ""
                vol = ""
                work_num = ""

            # 解析页码栏行
            # 支持两种格式: p0749c22 或 0749c22
            if page_part.startswith('p'):
                page_match = re.search(r'p(\d+)', page_part)
                page = page_match.group(1) if page_match else ""
            else:
                # 简化格式 0749c22，页码在开头
                page_match = re.search(r'^(\d+)', page_part)
                page = page_match.group(1) if page_match else ""

            col_match = re.search(r'([abc])', page_part)
            col = col_match.group(1) if col_match else ""
            col_name = {"a": "上栏", "b": "中栏", "c": "下栏"}.get(col, "")

            line_match = re.search(r'[abc](\d+)', page_part)
            line = line_match.group(1) if line_match else ""

            return {
                "canon": canon,
                "vol": vol,
                "work": work_num,
                "page": page,
                "col": col,
                "col_name": col_name,
                "line": line,
                "formatted": f"册{vol}, 经{work_num}, 页{page}, {col_name}{line}行"
            }
        except Exception:
            return None

    def _format_citation(self, title: str, keyword: str, work: str, vol: str = "", lb: str = "", version: str = "2025.R3") -> str:
        """生成标准 CBETA 引用格式."""
        # 册号优先使用传入的 vol（从 work_info 获取）
        # 如果没有传入 vol，则从 work 字串解析（work 格式如 T08n0235 或 T0235）
        canon = work[0] if work else ""

        if not vol and work:
            # 尝试从 file 格式（T08n0235）解析册号
            vol_match = re.search(r'[A-Z](\d+)', work)
            if vol_match:
                vol = canon + vol_match.group(1)

        # 解析经号（去掉 n 前缀）
        work_num = ""
        work_match = re.search(r'n?(\d+)', work)
        work_num = work_match.group(1) if work_match else work[1:]

        # 解析页码
        page_str = ""
        if lb:
            page_info = self._parse_linehead(lb)
            if page_info:
                page_str = f"p. {page_info.get('page', '')}{page_info.get('col', '')}{page_info.get('line', '')}"
            else:
                # 简化解析
                page_match = re.search(r'(\d+)([abc])(\d+)', lb)
                if page_match:
                    page_str = f"p. {page_match.group(1)}{page_match.group(2)}{page_match.group(3)}"

        # 构建引用格式
        # 《经名》：「引用文」(CBETA 版本, 册号, no. 经号, p. 页码栏行)
        parts = [f"《{title}》：「{keyword}」"]
        parts.append(f"(CBETA {version}")
        if vol:
            # vol 已经是 T08 格式（包含 canon），直接使用
            parts.append(f", {vol}")
        elif canon:
            # 如果没有 vol，只有 canon
            parts.append(f", {canon}")
        if work_num:
            parts.append(f", no. {work_num}")
        if page_str:
            parts.append(f", {page_str}")
        parts.append(")")

        return "".join(parts)

    def batch_find_sources(self, keywords: List[str], rows: int = 20) -> List[Dict]:
        """批量出处查找 - 输入多个关键词，返回结构化结果列表.

        Args:
            keywords: 关键词列表（多个经文句子）
            rows: 每个关键词搜索的结果数量

        Returns:
            [
                {
                    "keyword": 关键词,
                    "success": True/False,
                    "source": {work, title, citation, ...} 或 None,
                    "error": 错误信息（如果失败）
                },
                ...
            ]

        Example:
            >>> api = CbetaAPI()
            >>> results = api.batch_find_sources([
            ...     "应无所住而生其心",
            ...     "色即是空",
            ...     "一切有为法如梦幻泡影"
            ... ])
        """
        results = []
        for keyword in keywords:
            try:
                source = self.find_source(keyword, rows=rows)
                if "error" in source:
                    results.append({
                        "keyword": keyword,
                        "success": False,
                        "source": None,
                        "error": source.get("error")
                    })
                else:
                    results.append({
                        "keyword": keyword,
                        "success": True,
                        "source": source,
                        "error": None
                    })
            except Exception as e:
                results.append({
                    "keyword": keyword,
                    "success": False,
                    "source": None,
                    "error": str(e)
                })
        return results

    def find_sources_summary(self, keywords: List[str], rows: int = 20) -> Dict:
        """批量出处查找摘要 - 返回统计和详细结果.

        Returns:
        {
            "total": 总关键词数,
            "success_count": 成功数,
            "failed_count": 失败数,
            "results": 详细结果列表,
            "citations": 所有成功引用的列表
        }
        """
        results = self.batch_find_sources(keywords, rows)

        success_count = sum(1 for r in results if r["success"])
        failed_count = len(results) - success_count

        citations = []
        for r in results:
            if r["success"] and r["source"]:
                citations.append(r["source"].get("citation", ""))

        return {
            "total": len(keywords),
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results,
            "citations": citations
        }

        # 取最早的（已按 time_from 排序）
        best_match = sutra_results[0]
        work = best_match.get("work", "")
        title = best_match.get("title", "")
        byline = best_match.get("byline", "")
        time_dynasty = best_match.get("time_dynasty", "")
        time_from = best_match.get("time_from")
        time_to = best_match.get("time_to")
        juan = best_match.get("juan", 1) or 1
        canon = work[0] if work else "T"

        # 使用快速页码映射表（如果有）
        if work in COMMON_WORK_PAGES:
            start_page, end_page, vol = COMMON_WORK_PAGES[work]
            linehead_start = f"{vol}n{work[1:]}_p{start_page:04d}a01"
            # 估算结束行（每页约600字，每行约25字）
            estimated_lines = (end_page - start_page) * 28 + 1
            linehead_end = f"{vol}n{work[1:]}_p{end_page:04d}c{min(26, estimated_lines)}"
        else:
            # 使用 goto API 获取起始行号
            linehead_start = self.get_juan_start(canon, work, juan)
            if not linehead_start:
                # 无法获取行号，返回基本信息
                work_num = work[1:] if work else ""
                return {
                    "keyword": keyword,
                    "work": work,
                    "title": title,
                    "byline": byline,
                    "time_dynasty": time_dynasty,
                    "time_from": time_from,
                    "time_to": time_to,
                    "citation": f"《{title}》(CBETA {CBETA_VERSION}, {canon}, no. {work_num})",
                    "note": "无法定位精确页码"
                }
            linehead_end = None

        # 获取行内容
        lines = self.get_lines(linehead_start=linehead_start, linehead_end=linehead_end)

        # 合并文本
        full_text = ""
        line_map = []  # (累积字符数, linehead)
        for line in lines:
            linehead = line.get("linehead", "")
            html = line.get("html", "")
            # 去除 HTML 标签
            text = re.sub(r'<[^>]+>', '', html)
            full_text += text
            line_map.append((len(full_text), linehead))

        if not full_text:
            return {
                "keyword": keyword,
                "work": work,
                "title": title,
                "citation": f"《{title}》(CBETA {CBETA_VERSION}, {canon})",
                "note": "无法获取全文"
            }

        # 定位关键词（使用转换后的繁体关键词）
        search_keyword = search_info.get("converted_query", keyword)
        pos = self.find_keyword_in_text(full_text, search_keyword)

        if not pos:
            return {
                "keyword": keyword,
                "work": work,
                "title": title,
                "byline": byline,
                "time_dynasty": time_dynasty,
                "citation": f"《{title}》(CBETA {CBETA_VERSION}, {canon})",
                "note": "关键词未在文本中找到"
            }

        # 找到关键词所在行
        start_pos, end_pos, match_mode = pos
        start_linehead = None
        end_linehead = None

        for cum_pos, linehead in line_map:
            if cum_pos >= start_pos and start_linehead is None:
                start_linehead = linehead
            if cum_pos >= end_pos and end_linehead is None:
                end_linehead = linehead
                break

        if not start_linehead:
            start_linehead = linehead_start
        if not end_linehead:
            end_linehead = start_linehead

        # 解析页码
        start_info = self.parse_linehead(start_linehead)
        end_info = self.parse_linehead(end_linehead)

        if not start_info:
            return {
                "keyword": keyword,
                "work": work,
                "title": title,
                "citation": f"《{title}》(CBETA {CBETA_VERSION}, {canon})",
                "note": "无法解析页码"
            }

        end_info = end_info or start_info

        # 生成页码格式
        if start_info == end_info:
            page_str = f"{start_info['page']}{start_info['col']}{start_info['line']}"
        elif start_info['page'] == end_info['page'] and start_info['col'] == end_info['col']:
            # 同页同栏跨行
            page_str = f"{start_info['page']}{start_info['col']}{start_info['line']}-{end_info['line']}"
        elif start_info['page'] == end_info['page']:
            # 同页跨栏
            page_str = f"{start_info['page']}{start_info['col']}{start_info['line']}-{end_info['col']}{end_info['line']}"
        else:
            # 跨页
            page_str = f"{start_info['page']}{start_info['col']}{start_info['line']}-{end_info['page']}{end_info['col']}{end_info['line']}"

        # 生成标准引用格式
        vol_str = f"{start_info['canon']}{start_info['vol']}"
        work_str = start_info['work']

        citation = f"《{title}》：「{keyword}」(CBETA {CBETA_VERSION}, {vol_str}, no. {work_str}, p. {page_str})"

        return {
            "keyword": keyword,
            "work": work,
            "title": title,
            "byline": byline,
            "time_dynasty": time_dynasty,
            "time_from": time_from,
            "time_to": time_to,
            "canon": start_info['canon'],
            "vol": start_info['vol'],
            "page": page_str,
            "match_mode": match_mode,
            "citation": citation
        }

    # ── 异步方法 ────────────────────────────────────────────────

    async def batch_find_sources_async(self, keywords: List[str], rows: int = 20,
                                        max_concurrent: int = 5) -> List[Dict]:
        """异步批量出处查找 - 并发执行，提速3-5倍.

        Args:
            keywords: 关键词列表
            rows: 每个关键词搜索的结果数量
            max_concurrent: 最大并发数（默认5，避免API过载）

        Returns:
            与 batch_find_sources 相同格式

        Example:
            >>> import asyncio
            >>> api = CbetaAPI()
            >>> results = await api.batch_find_sources_async([
            ...     "应无所住而生其心",
            ...     "色即是空"
            ... ])
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _find_one(keyword: str) -> Dict:
            async with semaphore:
                # 使用线程池执行同步方法（requests不支持async）
                loop = asyncio.get_event_loop()
                try:
                    source = await loop.run_in_executor(None, self.find_source, keyword, rows)
                    if "error" in source:
                        return {
                            "keyword": keyword,
                            "success": False,
                            "source": None,
                            "error": source.get("error")
                        }
                    else:
                        return {
                            "keyword": keyword,
                            "success": True,
                            "source": source,
                            "error": None
                        }
                except Exception as e:
                    return {
                        "keyword": keyword,
                        "success": False,
                        "source": None,
                        "error": str(e)
                    }

        tasks = [_find_one(kw) for kw in keywords]
        results = await asyncio.gather(*tasks)
        return list(results)

    def batch_find_sources_concurrent(self, keywords: List[str], rows: int = 20,
                                       max_concurrent: int = 5) -> List[Dict]:
        """同步调用异步批量查找 - 方便不熟悉async的用户使用.

        Example:
            >>> api = CbetaAPI()
            >>> results = api.batch_find_sources_concurrent([
            ...     "应无所住而生其心",
            ...     "色即是空"
            ... ], max_concurrent=3)
        """
        return asyncio.run(self.batch_find_sources_async(keywords, rows, max_concurrent))


# ── 全局实例和快捷函数 ────────────────────────────────────────────────

_api_instance: Optional[CbetaAPI] = None


def get_api() -> CbetaAPI:
    """获取全局 API 实例."""
    global _api_instance
    if _api_instance is None:
        _api_instance = CbetaAPI()
    return _api_instance


def find_source(keyword: str) -> Dict:
    """出处查找快捷函数."""
    return get_api().find_source(keyword)


def batch_find_sources(keywords: List[str]) -> List[Dict]:
    """批量出处查找快捷函数."""
    return get_api().batch_find_sources(keywords)


def find_sources_summary(keywords: List[str]) -> Dict:
    """批量出处查找摘要快捷函数."""
    return get_api().find_sources_summary(keywords)


def smart_search(q: str, rows: int = 20) -> Tuple[Dict, Dict]:
    """智能搜索快捷函数."""
    return get_api().smart_search(q, rows)


def get_work_info(work: str) -> Optional[Dict]:
    """获取佛典信息快捷函数."""
    return get_api().get_work_info(work)


def search_kwic(q: str, work: str = None, juan: int = None) -> Dict:
    """KWIC 搜索快捷函数."""
    return get_api().search_kwic(q, work=work, juan=juan)


def export_all_works() -> List[Dict]:
    """导出全部佛典快捷函数."""
    return get_api().export_all_works()


# ── 测试示例 ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== CBETA API 测试 ===\n")

    api = CbetaAPI()

    # 测试健康检查
    print("1. 健康检查:")
    health = api.health()
    print(f"   状态: {health.get('status', 'OK')}\n")

    # 测试统计
    print("2. 统计报表:")
    stats = api.report_total()
    total = stats.get('total', {})
    print(f"   佛典数: {total.get('works_all', 'N/A')}")
    print(f"   卷数: {total.get('juans_all', 'N/A')}")
    print(f"   字数: {total.get('cjk_chars_all', 'N/A')}\n")

    # 测试出处查找
    print("3. 出处查找:")
    result = api.find_source("应无所住而生其心")
    print(f"   引用: {result.get('citation', 'N/A')}\n")

    # 测试智能搜索
    print("4. 智能搜索:")
    result, info = api.smart_search("般若波罗蜜", rows=5)
    print(f"   搜索类型: {info['search_type']}")
    print(f"   结果数: {info['num_found']}\n")

    # 测试 KWIC
    print("5. KWIC 搜索:")
    kwic = api.search_kwic("应无所住", work="T0235")
    results = kwic.get('results', [])
    if results:
        print(f"   找到 {len(results)} 个上下文片段\n")

    # 测试导出
    print("6. 导出佛典:")
    works = api.export_all_works()
    print(f"   导出 {len(works)} 部佛典\n")

    # 测试缓存统计
    print("7. 缓存统计:")
    cache_stats = api._cache.stats()
    print(f"   缓存条目: {cache_stats['entries']}\n")

    print("=== 测试完成 ===")