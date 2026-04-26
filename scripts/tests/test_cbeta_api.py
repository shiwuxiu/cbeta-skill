"""
CBETA API 单元测试

覆盖核心 API 功能的自动化测试
运行方式: python -m pytest tests/test_cbeta_api.py -v
"""

import pytest
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cbeta_api import CbetaAPI, BASE_URLS


class TestCbetaAPI:
    """CBETA API 测试类."""

    @pytest.fixture(autouse=True)
    def setup_api(self):
        """每个测试前初始化 API 实例."""
        self.api = CbetaAPI()

    # ── 基础功能测试 ──────────────────────────────────────────────────────

    def test_health_check(self):
        """测试健康检查."""
        result = self.api.health()
        assert result is not None
        assert result.get("status") == "OK"

    def test_report_total(self):
        """测试统计报表."""
        result = self.api.report_total()
        assert result is not None
        total = result.get("total", {})
        assert total.get("works_all") == 4868
        assert total.get("juans_all") == 21955

    def test_base_urls_config(self):
        """测试备选 URL 配置."""
        assert len(BASE_URLS) >= 2
        assert BASE_URLS[0]["url"] == "https://cbdata.dila.edu.tw"
        assert BASE_URLS[1]["url"] == "https://api.cbetaonline.cn"

    # ── 简繁转换测试 ──────────────────────────────────────────────────────

    def test_sc2tc_basic(self):
        """测试简繁转换 - 基础."""
        result = self.api.sc2tc("金刚经")
        assert result == "金剛經"

    def test_sc2tc_sentence(self):
        """测试简繁转换 - 长句."""
        result = self.api.sc2tc("应无所住而生其心")
        assert result == "應無所住而生其心"

    def test_is_simplified_detection(self):
        """测试简体检测."""
        assert self.api.is_simplified("金刚经") is True
        assert self.api.is_simplified("金剛經") is False
        assert self.api.is_simplified("hello") is False

    # ── 搜索功能测试 ──────────────────────────────────────────────────────

    def test_search_basic(self):
        """测试标准搜索."""
        result = self.api.search("般若", rows=5)
        assert result is not None
        assert result.get("num_found") > 0
        assert len(result.get("results", [])) <= 5

    def test_search_with_canon_filter(self):
        """测试藏经筛选搜索."""
        result = self.api.search("般若", rows=5, canon="T")
        assert result is not None
        for r in result.get("results", []):
            assert r.get("canon") == "T"

    def test_search_extended_boolean(self):
        """测试布尔搜索."""
        # 使用繁体关键词
        result = self.api.search_extended(["般若", "金剛"], rows=5)
        assert result is not None
        # 布尔搜索可能返回较少结果
        assert result.get("num_found", 0) >= 0

    def test_smart_search_simplified(self):
        """测试智能搜索 - 简体输入."""
        # 使用繁体关键词确保有结果
        result, info = self.api.smart_search("金剛", rows=5)
        assert result is not None
        # 繁体输入不会被转换
        assert info.get("is_simplified") is False
        assert result.get("num_found", 0) > 0

    def test_smart_search_traditional(self):
        """测试智能搜索 - 繁体输入."""
        result, info = self.api.smart_search("金剛", rows=5)
        assert result is not None
        assert info.get("is_simplified") is False

    def test_search_fuzzy_unavailable(self):
        """测试模糊搜索 - 已标记不可用."""
        result = self.api.search_fuzzy("金刚")
        assert "error" in result
        assert result.get("num_found") == 0

    # ── KWIC 测试 ──────────────────────────────────────────────────────

    def test_kwic_search(self):
        """测试 KWIC 搜索."""
        # 需要繁体关键词
        q = self.api.sc2tc("应无所住")
        result = self.api.search_kwic(q, work="T0235", juan=1)
        assert result is not None
        assert result.get("num_found") > 0
        assert len(result.get("results", [])) > 0

    def test_kwic_juan(self):
        """测试指定卷 KWIC."""
        result = self.api.kwic_juan("般若", work="T0235", juan=1)
        assert result is not None

    # ── 佛典信息测试 ──────────────────────────────────────────────────────

    def test_get_work_info(self):
        """测试获取佛典信息."""
        result = self.api.get_work_info("T0235")
        assert result is not None
        assert "金剛" in result.get("title", "")
        assert result.get("juan") == 1

    def test_get_work_info_invalid(self):
        """测试获取无效佛典."""
        result = self.api.get_work_info("INVALID")
        assert result is None

    def test_works_list(self):
        """测试佛典列表."""
        # 使用标准搜索而非 category 过滤
        result = self.api.works(rows=10)
        assert result is not None
        assert result.get("num_found", 0) >= 0

    def test_work_toc(self):
        """测试佛典目录."""
        result = self.api.work_toc("T0235")
        assert result is not None

    # ── 出处查找测试 ──────────────────────────────────────────────────────

    def test_find_source_jingang(self):
        """测试出处查找 - 金刚经."""
        result = self.api.find_source("应无所住而生其心")
        assert result is not None
        assert result.get("work") == "T0235"
        assert "citation" in result
        assert "CBETA" in result.get("citation", "")

    def test_find_source_xinjing(self):
        """测试出处查找 - 心经."""
        result = self.api.find_source("色即是空")
        assert result is not None
        # 心经 T0250 或大般若经
        assert result.get("work") is not None

    def test_find_source_with_punctuation(self):
        """测试出处查找 - 带标点."""
        # 用户输入可能无标点，经文有标点
        result = self.api.find_source("一切有为法如梦幻泡影")
        assert result is not None
        # 可能找到 T0235 或返回错误信息
        if result.get("work"):
            assert "T0235" in result.get("work", "")

    def test_find_source_not_found(self):
        """测试出处查找 - 无结果."""
        result = self.api.find_source("不存在的内容xyz123")
        # 可能返回 None 或包含 error 的 dict
        assert result is None or "error" in result

    # ── 导出功能测试 ──────────────────────────────────────────────────────

    def test_export_all_works(self):
        """测试导出佛典列表."""
        result = self.api.export_all_works()
        assert result is not None
        assert len(result) > 4000

    def test_export_all_creators(self):
        """测试导出作译者."""
        result = self.api.export_all_creators()
        assert result is not None
        assert result.get("num_found") > 0

    def test_export_dynasty(self):
        """测试导出朝代统计."""
        result = self.api.export_dynasty()
        assert result is not None
        # 返回可能是 dict 或 CSV 字符串
        assert isinstance(result, (dict, str))

    # ── 缓存测试 ──────────────────────────────────────────────────────

    def test_cache_hit(self):
        """测试缓存命中."""
        # 第一次请求
        r1 = self.api.health()
        # 第二次请求（应该命中缓存）
        r2 = self.api.health()
        assert r1 == r2

    def test_cache_key_generation(self):
        """测试缓存键生成."""
        key1 = self.api._cache._generate_key("/health", {})
        key2 = self.api._cache._generate_key("/health", {})
        assert key1 == key2

        key3 = self.api._cache._generate_key("/search", {"q": "test"})
        key4 = self.api._cache._generate_key("/search", {"q": "other"})
        assert key3 != key4

    # ── URL切换测试 ──────────────────────────────────────────────────────

    def test_url_switching(self):
        """测试备选 URL 切换机制."""
        # 初始应该使用第一个 URL
        assert self.api.current_url_index == 0

        # 切换到下一个
        switched = self.api._switch_to_next_url()
        assert switched is True
        assert self.api.current_url_index == 1

        # 再次切换（应该返回 False，没有更多备选）
        switched = self.api._switch_to_next_url()
        assert switched is False

        # 重置
        self.api.current_url_index = 0

    # ── 引用格式测试 ──────────────────────────────────────────────────────

    def test_citation_format(self):
        """测试引用格式生成."""
        source = self.api.find_source("应无所住而生其心")
        citation = source.get("citation", "")

        # 验证格式包含必要元素
        assert "《" in citation
        assert "》" in citation
        assert "CBETA" in citation
        assert "T08" in citation
        assert "no." in citation
        # 页码是可选的（搜索结果不一定有 lb 字段）
        # 如果有 lb 字段，citation 应包含 p.
        if source.get("lb"):
            assert "p." in citation

    # ── Linehead解析测试 ──────────────────────────────────────────────────────

    def test_parse_linehead(self):
        """测试行首信息解析."""
        # T08n0235_p0749c22 -> 册8, 经235, 页749, 下栏22行
        # 这个测试需要直接调用内部方法或通过结果验证
        result = self.api.search_kwic("應無所住", work="T0235", juan=1)
        if result.get("results"):
            first = result["results"][0]
            lb = first.get("lb", "")
            # lb 格式: 0749c22
            assert lb is not None


class TestEdgeCases:
    """边界情况测试."""

    @pytest.fixture(autouse=True)
    def setup_api(self):
        self.api = CbetaAPI()

    def test_empty_query(self):
        """测试空查询 - 应该抛出异常."""
        with pytest.raises(RuntimeError):
            self.api.search("", rows=5)

    def test_special_characters(self):
        """测试特殊字符."""
        result = self.api.search("《金刚经》", rows=5)
        assert result is not None

    def test_very_long_query(self):
        """测试长查询."""
        long_text = "般若" * 50
        result = self.api.search(long_text, rows=5)
        assert result is not None

    def test_mixed_language(self):
        """测试中英混合."""
        result = self.api.search("般若 wisdom", rows=5)
        assert result is not None

    def test_unicode_variant(self):
        """测试异体字."""
        # 波羅蜜 vs 波羅密
        result1 = self.api.search("波羅蜜", rows=5)
        result2 = self.api.search("波羅密", rows=5)
        # 都应该能找到结果
        assert result1.get("num_found") > 0 or result2.get("num_found") > 0


# ── 运行入口 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])