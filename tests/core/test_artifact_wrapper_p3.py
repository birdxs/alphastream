# Input: wrap_shipping_v2/wrap_esg_v2/wrap_hiring_v2/wrap_corporate_network_v2/wrap_alt_data_v2
# Output: 前端 Artifact 契约字段验证 (shipping/esg/hiring/corporate_network/alt_data)
# Pos: tests/core/test_artifact_wrapper_p3.py — F2 P3 Artifact 包装单元测试 [NEW-FILE:#20260415-35]
"""
测试 app/core/artifact_wrapper.py 新增的 5 个 P3 Artifact 包装函数 (v2 后缀),
确保后端 wrap_*_v2() 输出字段严格对齐前端 frontend/src/components/artifacts/*.tsx 契约.

测试矩阵 (15+ case):
  - wrap_shipping_v2:        happy path / 缺字段 / 空输入 / list 输入
  - wrap_esg_v2:             多源 scores+cdp+disclosures / 最小 scores / 全空
  - wrap_hiring_v2:          完整 postings+trend / 派生 monthly_trend / 空 / yoy_change 计算
  - wrap_corporate_network_v2: 完整 details+network / 仅 details / 全空
  - wrap_alt_data_v2:        聚合4子域 / 部分子域 / 自动识别 wrap_v2 嵌套返回

所有测试 mock-only, 不启服务, 不触网.
"""
import pandas as pd
import pytest

from app.core.artifact_wrapper import (
    wrap_shipping_v2,
    wrap_esg_v2,
    wrap_hiring_v2,
    wrap_corporate_network_v2,
    wrap_alt_data_v2,
)


# ============================================================
# wrap_shipping_v2
# ============================================================
class TestWrapShipping:

    def test_happy_path_full_dataframes(self):
        bdi_df = pd.DataFrame([
            {"date": "2026-03-01", "value": 1200.5, "indicator": "BDI", "source": "te"},
            {"date": "2026-03-02", "value": 1250.0, "indicator": "BDI", "source": "te"},
        ])
        port_df = pd.DataFrame([
            {"date": "2026-03", "port": "shanghai", "value": 4250.0, "unit": "万TEU", "indicator": "throughput"},
            {"date": "2026-03", "port": "ningbo", "value": 3180.0, "unit": "万TEU", "indicator": "throughput"},
        ])
        ais_df = pd.DataFrame([
            {"mmsi": "123456", "name": "MV ALPHA", "ship_type": "container", "lat": 31.2, "lon": 121.5, "sog": 12.3},
        ])

        result = wrap_shipping_v2("招商局", bdi_df=bdi_df, port_df=port_df, ais_df=ais_df)

        assert result["type"] == "shipping"
        assert "招商局" in result["title"]
        assert result["stock_name"] == "招商局"
        assert set(result["data"].keys()) >= {"bdi_series", "port_throughput", "ais_vessels", "ais_count", "port_name"}
        assert len(result["data"]["bdi_series"]) == 2
        # 契约字段
        assert {"date", "value", "indicator", "source"} <= set(result["data"]["bdi_series"][0].keys())
        assert isinstance(result["data"]["bdi_series"][0]["value"], float)
        assert result["data"]["ais_count"] == 1
        assert result["data"]["port_name"] == "shanghai"

    def test_missing_optional_df(self):
        """port_df/ais_df 缺失, 仅 BDI"""
        bdi_df = pd.DataFrame([{"date": "2026-03-01", "value": 1100, "indicator": "BDI", "source": "x"}])
        result = wrap_shipping_v2("测试", bdi_df=bdi_df)
        assert result["type"] == "shipping"
        assert len(result["data"]["bdi_series"]) == 1
        assert result["data"]["port_throughput"] == []
        assert result["data"]["ais_vessels"] == []
        assert result["data"]["ais_count"] == 0
        assert result["data"]["port_name"] == ""

    def test_empty_all_inputs(self):
        result = wrap_shipping_v2("空", bdi_df=None, port_df=None, ais_df=None)
        assert result["type"] == "shipping"
        assert result["data"]["bdi_series"] == []
        assert result["data"]["port_throughput"] == []
        assert result["data"]["ais_count"] == 0

    def test_list_input_compat(self):
        """支持 list[dict] 输入 (adapter 可能返回非DF)"""
        bdi_list = [{"date": "2026-03-01", "value": 1200, "indicator": "BDI", "source": "x"}]
        result = wrap_shipping_v2("X", bdi_df=bdi_list)
        assert len(result["data"]["bdi_series"]) == 1


# ============================================================
# wrap_esg_v2
# ============================================================
class TestWrapEsg:

    def test_happy_path_full(self):
        scores = {
            "source": "esgbook", "ticker": "AAPL", "company": "Apple Inc.",
            "esg_score": 72, "e_score": 68, "s_score": 75, "g_score": 74,
            "grade": "A", "as_of": "2026-01",
        }
        disclosures = {
            "cik": "0000320193",
            "tags": {"us-gaap:GHGEmissions": [{"end": "2025-12-31", "val": 100}]},
            "scope1_latest": 12.5, "scope2_latest": 45.0, "scope3_latest": None,
        }
        cdp = {
            "company": "Apple Inc.", "year": 2025,
            "climate_score": "A", "disclosures": [{"tag": "TCFD", "label": "TCFD框架", "filing_date": "2025-11-10"}],
            "source": "cdp",
        }

        result = wrap_esg_v2("Apple Inc.", scores=scores, disclosures=disclosures, cdp=cdp)

        assert result["type"] == "esg"
        d = result["data"]
        # 顶层扁平字段
        assert d["esg_score"] == 72
        assert d["e_score"] == 68
        assert d["grade"] == "A"
        # primary
        assert d["primary"]["esg_score"] == 72
        assert d["primary"]["source"] == "esgbook"
        # sources 多源对比 (esgbook + cdp)
        assert len(d["sources"]) >= 2
        cdp_row = next(r for r in d["sources"] if r["source"] == "cdp")
        assert cdp_row["grade"] == "A"
        # climate_disclosures (scope1/2 + tags + cdp disclosures)
        tags = [c["tag"] for c in d["climate_disclosures"]]
        assert "Scope 1" in tags
        assert "Scope 2" in tags
        assert "TCFD" in tags

    def test_minimal_scores_only(self):
        scores = {"ticker": "MSFT", "esg_score": 65, "source": "esgbook"}
        result = wrap_esg_v2("Microsoft", scores=scores)
        assert result["type"] == "esg"
        assert result["data"]["esg_score"] == 65
        assert result["data"]["ticker"] == "MSFT"
        assert result["data"]["climate_disclosures"] == []
        # 有主评分故 sources 含一条
        assert len(result["data"]["sources"]) == 1

    def test_all_none(self):
        result = wrap_esg_v2("无数据", scores=None, disclosures=None, cdp=None)
        assert result["type"] == "esg"
        assert result["data"]["esg_score"] is None
        assert result["data"]["sources"] == []
        assert result["data"]["climate_disclosures"] == []
        assert result["data"]["company"] == "无数据"


# ============================================================
# wrap_hiring_v2
# ============================================================
class TestWrapHiring:

    def test_happy_path_with_trend(self):
        postings_df = pd.DataFrame([
            {"title": "AI Engineer", "company": "Apple Inc.", "location": "CA",
             "tags": "AI,Python,ML", "url": "http://x", "created_at": "2026-03-01", "source": "arbeitnow"},
            {"title": "iOS Dev", "company": "Apple Inc.", "location": "CA",
             "tags": "iOS,Swift", "url": "http://y", "created_at": "2026-03-15", "source": "arbeitnow"},
        ])
        trend_df = pd.DataFrame([{"month": f"2025-{m:02d}", "count": 100 + m} for m in range(1, 13)]
                                + [{"month": "2026-01", "count": 150}])

        result = wrap_hiring_v2("Apple Inc.", postings_df=postings_df, trend_df=trend_df)

        assert result["type"] == "hiring"
        d = result["data"]
        assert d["total_postings"] == 2
        assert d["company"] == "Apple Inc."
        assert len(d["items"]) == 2
        # monthly_trend: 用传入 trend_df
        assert len(d["monthly_trend"]) == 13
        # skill_distribution 从 tags 派生
        skill_names = [s["name"] for s in d["skill_distribution"]]
        assert "AI" in skill_names or "Python" in skill_names
        # expansion_level 合法
        assert d["expansion_level"] in ("low", "medium", "high")

    def test_derived_monthly_trend(self):
        """trend_df 缺失, 从 items.created_at 派生"""
        postings_df = pd.DataFrame([
            {"title": "A", "company": "X", "tags": "ML", "created_at": "2026-01-15"},
            {"title": "B", "company": "X", "tags": "ML", "created_at": "2026-01-20"},
            {"title": "C", "company": "X", "tags": "DL", "created_at": "2026-02-01"},
        ])
        result = wrap_hiring_v2("X", postings_df=postings_df)
        d = result["data"]
        months = [m["month"] for m in d["monthly_trend"]]
        assert "2026-01" in months
        assert "2026-02" in months
        # 2026-01 应计 2 条
        jan = next(m for m in d["monthly_trend"] if m["month"] == "2026-01")
        assert jan["count"] == 2

    def test_empty(self):
        result = wrap_hiring_v2("空公司", postings_df=None)
        d = result["data"]
        assert d["total_postings"] == 0
        assert d["items"] == []
        assert d["monthly_trend"] == []
        assert d["skill_distribution"] == []
        assert d["expansion_level"] == "low"

    def test_yoy_change_calc(self):
        """13+ 月数据应计算 yoy_change"""
        trend_df = pd.DataFrame([
            {"month": f"2025-{m:02d}", "count": 100} for m in range(1, 13)
        ] + [{"month": "2026-01", "count": 150}])
        result = wrap_hiring_v2("Y", postings_df=pd.DataFrame(), trend_df=trend_df)
        # 最新 150 vs 12月前 index=-13 也即 2025-01=100, yoy=50%
        assert result["data"]["yoy_change"] == 50.0
        assert result["data"]["expansion_level"] == "high"


# ============================================================
# wrap_corporate_network_v2
# ============================================================
class TestWrapCorporateNetwork:

    def test_happy_path_full(self):
        details = {
            "name": "Apple Inc.",
            "jurisdiction_code": "us_ca",
            "incorporation_date": "1977-01-03",
            "current_status": "Active",
            "company_number": "C0806592",
            "opencorporates_url": "https://opencorporates.com/companies/us_ca/C0806592",
        }
        network = {
            "company_id": "us_ca/C0806592",
            "parents": [],
            "children": [
                {"name": "Apple Europe Ltd", "jurisdiction_code": "gb", "company_number": "04905014"},
            ],
            "officers": [
                {"name": "Tim Cook", "position": "CEO", "start_date": "2011-08-24", "end_date": None},
            ],
        }

        result = wrap_corporate_network_v2("Apple Inc.", company_details=details, network=network)

        assert result["type"] == "corporate_network"
        d = result["data"]
        assert d["company_id"] == "us_ca/C0806592"
        assert d["company_name"] == "Apple Inc."
        assert d["jurisdiction_code"] == "us_ca"
        assert d["current_status"] == "Active"
        assert d["opencorporates_url"].startswith("https://")
        # parents/children/officers 契约字段
        assert d["parents"] == []
        assert len(d["children"]) == 1
        assert d["children"][0]["name"] == "Apple Europe Ltd"
        assert d["children"][0]["jurisdiction_code"] == "gb"
        assert len(d["officers"]) == 1
        assert d["officers"][0]["position"] == "CEO"

    def test_details_only_no_network(self):
        details = {
            "name": "X Corp", "jurisdiction_code": "us_de", "company_number": "123",
            "current_status": "Active",
        }
        result = wrap_corporate_network_v2("X Corp", company_details=details, network=None)
        d = result["data"]
        # company_id 由 jurisdiction/number 拼接
        assert d["company_id"] == "us_de/123"
        assert d["parents"] == []
        assert d["children"] == []
        assert d["officers"] == []

    def test_all_empty(self):
        result = wrap_corporate_network_v2("未知", company_details=None, network=None)
        d = result["data"]
        assert d["company_id"] == ""
        assert d["company_name"] == "未知"
        assert d["parents"] == []


# ============================================================
# wrap_alt_data_v2
# ============================================================
class TestWrapAltData:

    def test_aggregate_all_four(self):
        s = wrap_shipping_v2("X", bdi_df=pd.DataFrame([{"date": "2026-03-01", "value": 1200, "indicator": "BDI", "source": "s"}]))
        e = wrap_esg_v2("X", scores={"ticker": "X", "esg_score": 70, "source": "esgbook"})
        h = wrap_hiring_v2("X", postings_df=pd.DataFrame([{"title": "Dev", "company": "X", "tags": "ML", "created_at": "2026-03-01"}]))
        c = wrap_corporate_network_v2("X", company_details={"name": "X", "jurisdiction_code": "us_ca", "company_number": "1"}, network={"parents": [], "children": [], "officers": []})

        result = wrap_alt_data_v2("X", shipping=s, esg=e, hiring=h, corporate=c)

        assert result["type"] == "alt_data"
        assert result["stock_name"] == "X"
        d = result["data"]
        # 4 子域齐全, 且每个子域是 wrap_*_v2 的 data 部分(已自动提取)
        assert "shipping" in d and "bdi_series" in d["shipping"]
        assert "esg" in d and d["esg"]["esg_score"] == 70
        assert "hiring" in d and d["hiring"]["total_postings"] == 1
        assert "corporate" in d and d["corporate"]["company_name"] == "X"

    def test_partial_subsets(self):
        """仅 shipping + hiring, 其他子域缺省 → data 只含 2 个 key"""
        s = wrap_shipping_v2("Y")
        h = wrap_hiring_v2("Y")
        result = wrap_alt_data_v2("Y", shipping=s, hiring=h)
        d = result["data"]
        assert "shipping" in d
        assert "hiring" in d
        assert "esg" not in d
        assert "corporate" not in d

    def test_accept_raw_data_dict(self):
        """支持直接传入子 data dict (非 wrap_v2 包裹)"""
        raw_esg = {"ticker": "Z", "esg_score": 50, "sources": []}
        result = wrap_alt_data_v2("Z", esg=raw_esg)
        # 自动识别: 无 data 键, 直接作为子 data
        assert result["data"]["esg"]["ticker"] == "Z"
        assert result["data"]["esg"]["esg_score"] == 50

    def test_all_none(self):
        result = wrap_alt_data_v2("空")
        assert result["type"] == "alt_data"
        assert result["data"] == {}

    # [N1 2026-04-15 15:18 +08:00] stock_code 契约回归
    def test_stock_code_transmitted(self):
        """P1: stock_code 参数正确透传到 artifact.stock_code"""
        result = wrap_alt_data_v2("Apple Inc", stock_code="AAPL")
        assert result["stock_code"] == "AAPL"
        assert result["stock_name"] == "Apple Inc"

    def test_stock_code_fallback_to_name(self):
        """P1: 未传 stock_code 时 fallback 到 stock_name, 不返回 None"""
        result = wrap_alt_data_v2("600519")
        assert result["stock_code"] == "600519"
        assert result["stock_code"] is not None


def test_provenance_entry_no_price_fields():
    from app.core.artifact_wrapper import (
        build_provenance_entry,
        provenance_from_sources,
        merge_provenance,
        normalize_provenance_item,
        normalize_provenance_list,
    )
    e = build_provenance_entry(source='akshare', tool='get_stock_data', args={'code': '600519'})
    assert set(e.keys()) <= {'source', 'tool', 'ts', 'digest'}
    assert 'price' not in e and 'close' not in e
    lst = provenance_from_sources(['akshare', {'name': 'eastmoney'}], tool='get_stock_data')
    assert len(lst) == 2
    # 输出全部为结构化 dict（输入可接受 string，输出禁止裸 string）
    assert all(isinstance(x, dict) and x.get('source') for x in lst)
    m = merge_provenance(lst, lst)
    assert len(m) == 2  # dedupe
    # 与 scorecard 同一 schema：拒绝裸 string / 假价字段
    assert normalize_provenance_item("akshare") is None
    dirty = {"source": "akshare", "price": 1174.06, "last_price": 1, "tool": "kline"}
    clean = normalize_provenance_item(dirty)
    assert clean is not None
    assert "price" not in clean and "last_price" not in clean
    assert clean.get("source") == "akshare"
    mixed = normalize_provenance_list(
        ["bare", {"source": "a"}, {"source": "a"}, {"source": "b", "pe": 12}, None],
        max_items=10,
    )
    assert all(isinstance(x, dict) for x in mixed)
    assert [x["source"] for x in mixed] == ["a", "b"]
    # merge 混入裸 string 不泄漏
    m2 = merge_provenance(lst, ["should-drop", {"source": "wind", "price": 9.9}])
    assert all(isinstance(x, dict) for x in m2)
    assert not any("price" in x for x in m2)
    sources = {x["source"] for x in m2}
    assert "wind" in sources
    assert "should-drop" not in sources
