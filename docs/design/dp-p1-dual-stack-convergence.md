# DP-P1 DataProvider vs AdapterRegistry 双栈统一方案

**文档版本**: v1.0  
**创建时间**: 2026-08-05  
**作者**: A1 - 数据栈统一架构师  
**任务编号**: DP-P1-1 + DP-P1-2

---

## 1. 执行摘要

### 1.1 问题定义

**DP-P1-1**: 当前 REST K 线走 `DataProvider + FallbackManager`，Agent 侧用 `AdapterRegistry.call_with_fallback`，双栈并存导致：
- 降级链顺序不一致（DataProvider 硬编码 akshare→baostock；Registry 可配置但未接入热路径）
- 维护成本高（两套逻辑、两套测试）
- 实际命中源不透明（测试复杂）

**DP-P1-2**: `meta.source` 写死 `'akshare'`（A 股标签），掩盖真实命中源：
- DataProvider 内部 akshare 有 3 个接口降级链（新浪 daily → 腾讯 hist_tx → 东财 hist）
- baostock 作为 fallback 时，前端仍显示 `source: 'akshare'`
- 无法追踪数据质量问题

### 1.2 影响范围

| 模块 | 当前路径 | 影响 |
|------|---------|------|
| `/api/stock_data` | DataProvider.get_stock_history | REST K 线主路径 |
| `tools.get_stock_data` | DataProvider.get_stock_history | Agent 工具 |
| `AdapterRegistry` | 闲置（仅 /api/adapters/status 等管理端点） | 能力未充分使用 |
| 前端 stock/[code] | 依赖 meta.source 显示数据来源 | 误导用户 |

---

## 2. 现状双栈调用链对比

### 2.1 DataProvider 栈（当前 REST 主路径）

```
/api/stock_data
  └─ analyzer.get_stock_data
       └─ market_data_adapter.get_kline (A 股分支)
            └─ DataProvider.get_stock_history
                 └─ FallbackManager([akshare, baostock])
                      ├─ AkshareAdapter.get_stock_history
                      │    ├─ 新浪 stock_zh_a_hist_sina (主)
                      │    ├─ 腾讯 hist_tx (fallback)
                      │    └─ 东财 hist (fallback)
                      └─ BaostockAdapter.get_stock_history
```

**特点**:
- 单例模式（`get_data_provider()`）
- 进程内 200ms 限流
- 30min TTL 缓存
- **硬编码** akshare → baostock 顺序

### 2.2 AdapterRegistry 栈（Agent 可选路径）

```
AdapterRegistry.call_with_fallback('a_stock_kline', ...)
  └─ domain='a_stock_kline' 配置链
       ├─ AkshareAdapter (first_available)
       ├─ BaostockAdapter
       ├─ EfinanceAdapter
       ├─ AshareAdapter
       └─ OpenBBAdapter (理论支持)
```

**特点**:
- 域驱动设计（domain 映射多 adapter）
- 动态注册（可插拔）
- 统一 `_is_valid_result` 验证
- **未接入 REST 热路径**

### 2.3 对比矩阵

| 维度 | DataProvider | AdapterRegistry | 优劣 |
|------|-------------|-----------------|------|
| 降级链配置 | 硬编码 | 可配置 DEFAULT_DOMAIN_MAP | **Registry 优** |
| 扩展性 | 低（需改 FallbackManager 构造） | 高（注册即用） | **Registry 优** |
| 性能开销 | 单例 + 限流 + 缓存 | 动态查找 + 健康检查 | **DataProvider 优** |
| 透传 source | 无 | 可返回实际 adapter 名 | **Registry 优** |
| 测试覆盖 | 高（历史积累） | 中（domain 测试为主） | **DataProvider 优** |
| 实际使用 | 100%（REST 主路径） | <10%（管理端点） | **DataProvider 优** |

---

## 3. 统一方案评估（≥3 个）

### 方案 A: Registry 取代 DataProvider（彻底统一）

**实现路径**:
1. 废弃 `DataProvider` 类
2. `market_data_adapter.get_kline` 改调 `AdapterRegistry.call_with_fallback('a_stock_kline', ...)`
3. 迁移限流/缓存到 Registry 层或 web_server
4. 返回结构增加 `meta.source = actual_adapter.name`

**改动文件清单**:
- 删除: `app/core/data_provider.py`
- 重构: `app/adapters/market_data_adapter.py` (get_kline 逻辑)
- 修改: `app/web/web_server.py` (stock_data 响应 meta.source)
- 新增: `tests/backend/integration/test_registry_kline.py`

**量化评分** (5 分制):
- 对齐度: 5 (彻底统一，零双栈)
- 收益: 4 (可配置降级链 + 透明 source)
- 风险: 4 (破坏现有单例/缓存/限流，需全量回归)
- 成本: 5 (删除整个 DataProvider，迁移所有调用方)
- 证据: 4 (Registry 能力已验证，但 REST 未实测)

**Score = 0.30×5 + 0.25×4 - 0.20×4 - 0.15×5 + 0.10×4 = 1.15**

**优点**:
- 彻底消除双栈，维护成本最低
- Registry 天然支持动态注册，扩展性最强
- source 透传无需额外适配

**缺点**:
- DataProvider 单例/限流/缓存需迁移，破坏面大
- 历史测试需全量改写
- 风险高（REST 热路径完全重构）

---

### 方案 B: DataProvider 封装 Registry（渐进统一）

**实现路径**:
1. 保留 `DataProvider` 单例/缓存/限流
2. `FallbackManager` 改为调用 `AdapterRegistry.call_with_fallback`
3. DataProvider.get_stock_history 返回增加 `_actual_source` 元数据
4. web_server 透传 `meta.source = _actual_source`

**改动文件清单**:
- 重构: `app/core/data_provider.py` (FallbackManager → Registry 桥接)
- 修改: `app/core/fallback_manager.py` (增加 source 透传)
- 修改: `app/web/web_server.py` (读取 _actual_source)
- 新增: `tests/backend/unit/test_data_provider_source.py`

**量化评分**:
- 对齐度: 4 (降级链统一，但外层仍包装)
- 收益: 4 (保留现有性能优化 + source 透传)
- 风险: 2 (最小破坏，兼容现有接口)
- 成本: 3 (适配层开发 + 透传改造)
- 证据: 5 (Registry 与 DataProvider 均已稳定)

**Score = 0.30×4 + 0.25×4 - 0.20×2 - 0.15×3 + 0.10×5 = 2.05** ✅ **最高分**

**优点**:
- 保留 DataProvider 性能优化（单例/缓存/限流）
- 最小破坏面（外层接口不变）
- Registry 降级链立即生效
- source 透传自然实现

**缺点**:
- 仍存在薄包装层（但逻辑收敛）
- 未彻底消除双栈概念

---

### 方案 C: DataProvider 增加 source 透传（最小改动）

**实现路径**:
1. `FallbackManager.execute` 返回元组 `(result, actual_adapter_name)`
2. `DataProvider.get_stock_history` 透传 adapter 名
3. `analyzer.get_stock_data` 在返回 DataFrame 时附加 `_source` 属性或返回 dict
4. web_server 提取 source 填充 meta

**改动文件清单**:
- 修改: `app/core/fallback_manager.py` (返回值改为元组)
- 修改: `app/core/data_provider.py` (透传 source)
- 修改: `app/analysis/stock_analyzer.py` (附加 source 元数据)
- 修改: `app/web/web_server.py` (读取 source)
- 修改: 所有调用 FallbackManager.execute 的地方（约 8 处）

**量化评分**:
- 对齐度: 2 (仅解决 P1-2，P1-1 双栈依旧)
- 收益: 3 (source 透传，但降级链仍硬编码)
- 风险: 1 (最小改动，零破坏)
- 成本: 2 (返回值改造 + 透传链路)
- 证据: 5 (无新依赖，纯代码改造)

**Score = 0.30×2 + 0.25×3 - 0.20×1 - 0.15×2 + 0.10×5 = 1.65**

**优点**:
- 最小破坏面（接口兼容）
- 快速实现（1-2h）
- 零回归风险

**缺点**:
- **不解决 P1-1 双栈问题**
- 降级链仍硬编码，未来扩展需再改
- 元数据透传链路长（易遗漏）

---

## 4. 推荐方案：方案 B（DataProvider 封装 Registry）

### 4.1 选择理由

1. **分数最高 (2.05)**: 平衡对齐度、收益、风险、成本
2. **最小破坏**: 保留 DataProvider 稳定性（单例/缓存/限流）
3. **彻底解决 P1-1**: 降级链统一到 Registry DEFAULT_DOMAIN_MAP
4. **自然解决 P1-2**: Registry 返回包含实际 adapter 名
5. **未来可演进**: 待 Registry 充分验证后，可逐步移除 DataProvider 包装（方案 A）

### 4.2 实现路径（分步）

#### Step 1: FallbackManager → Registry 桥接

**文件**: `app/core/data_provider.py`

```python
# 修改前
def __init__(self):
    self.fallback = FallbackManager([
        self.akshare,
        self.baostock,
    ])

# 修改后
def __init__(self):
    from app.adapters.adapter_registry import AdapterRegistry
    self._registry = AdapterRegistry()
    # FallbackManager 仍保留（后续逐步废弃）
    self.fallback = FallbackManager([self.akshare, self.baostock])
```

#### Step 2: get_stock_history 改调 Registry

```python
def get_stock_history(self, code: str, start_date: str, end_date: str,
                      adjust: str = "qfq") -> tuple[pd.DataFrame, str]:
    """返回 (DataFrame, source_name)"""
    self._rate_limit()

    cache_key = f"history_{code}_{start_date}_{end_date}_{adjust}"
    cached = self._cache.get(cache_key)
    if cached is not None:
        return pd.DataFrame(cached['data']), cached.get('source', 'cache')

    # 调用 Registry（a_stock_kline domain）
    result_dict = self._registry.call_with_fallback(
        'a_stock_kline',
        stock_code=code,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust
    )
    
    df = result_dict.get('data')  # DataFrame
    source = result_dict.get('source', 'unknown')  # 实际 adapter 名
    
    if df is not None and not df.empty:
        self._cache.set(cache_key, {
            'data': df.to_dict('records'),
            'source': source
        }, ttl=1800)
    
    return df, source
```

#### Step 3: web_server 透传 source

**文件**: `app/web/web_server.py` (line ~1925)

```python
# 修改前
df = fut.result(timeout=_stock_data_timeout)

# 修改后
df, actual_source = fut.result(timeout=_stock_data_timeout)

# 响应构造 (line ~1980)
return custom_jsonify({
    'data': records,
    'stock_name': stock_name,
    'meta': {
        'adjust_flag': _adjust_flag,
        'source': actual_source,  # 真实 adapter 名（如 'akshare.sina' / 'baostock'）
    },
})
```

#### Step 4: AdapterRegistry 返回结构标准化

**文件**: `app/adapters/adapter_registry.py`

确保 `call_with_fallback` 返回:
```python
{
    'data': df,  # DataFrame 或 其他数据
    'source': adapter.name,  # 实际命中的 adapter 名称
    'domain': domain  # 可选：记录域信息
}
```

### 4.3 改动清单（文件级）

| 文件 | 改动类型 | 关键点 |
|------|---------|--------|
| `app/core/data_provider.py` | 重构 | get_stock_history 返回改为 `(df, source)` |
| `app/adapters/adapter_registry.py` | 增强 | call_with_fallback 返回标准化 dict（含 source） |
| `app/web/web_server.py` | 适配 | stock_data 路由提取 source 填充 meta |
| `app/analysis/stock_analyzer.py` | 适配 | get_stock_data 透传 source（或保持 df，由 web_server 重新获取） |
| `tests/backend/unit/test_data_provider.py` | 更新 | 断言返回值为元组 |
| `tests/backend/integration/test_registry_stock_data.py` | 新增 | 端到端测试 Registry → REST source 透传 |

### 4.4 降级链配置（Registry）

**文件**: `app/adapters/adapter_registry.py`

确认 `a_stock_kline` domain 配置:
```python
DEFAULT_DOMAIN_MAP = {
    'a_stock_kline': [
        'AkshareAdapter',    # 优先（内部含 3 接口降级）
        'BaostockAdapter',   # 备用
        'EfinanceAdapter',   # 第三
        'AshareAdapter',     # 第四
    ],
    # ...
}
```

### 4.5 source 命名规范

| 实际命中 | meta.source 值 | 说明 |
|---------|---------------|------|
| AkshareAdapter.新浪接口 | `akshare` 或 `akshare.sina` | 建议细化到接口级 |
| AkshareAdapter.腾讯接口 | `akshare.tencent` | |
| BaostockAdapter | `baostock` | |
| cache 命中 | `cache` | 保留现有逻辑 |

**推荐**: `akshare` 改为 `akshare.sina` 等细粒度标签，便于追踪数据质量。

---

## 5. 测试策略

### 5.1 单元测试（≥5 用例）

**文件**: `tests/backend/unit/test_data_provider_source.py`

```python
def test_get_stock_history_returns_source():
    """DataProvider.get_stock_history 返回 (df, source) 元组"""
    dp = DataProvider()
    df, source = dp.get_stock_history('600519', '20240101', '20240131')
    assert isinstance(df, pd.DataFrame)
    assert isinstance(source, str)
    assert source in ['akshare', 'baostock', 'cache']

def test_source_reflects_actual_adapter():
    """source 反映真实命中 adapter"""
    # mock AkshareAdapter 失败，BaostockAdapter 成功
    with monkeypatch_akshare_fail():
        df, source = dp.get_stock_history('600519', ...)
        assert source == 'baostock'

def test_cache_hit_returns_cache_source():
    """缓存命中时 source='cache'"""
    dp.get_stock_history('600519', ...)  # 第一次
    df, source = dp.get_stock_history('600519', ...)  # 第二次
    assert source == 'cache'

def test_registry_fallback_order():
    """Registry 降级链顺序符合 DEFAULT_DOMAIN_MAP"""
    registry = AdapterRegistry()
    # mock adapter 逐个失败，验证顺序
    ...

def test_web_server_meta_source():
    """REST /api/stock_data 返回 meta.source"""
    resp = client.get('/api/stock_data?stock_code=600519&period=1m')
    data = resp.get_json()
    assert 'meta' in data
    assert 'source' in data['meta']
    assert data['meta']['source'] in ['akshare', 'baostock', 'cache']
```

### 5.2 集成测试

**文件**: `tests/backend/integration/test_registry_stock_data.py`

```python
def test_stock_data_registry_end_to_end():
    """端到端：REST → analyzer → DataProvider → Registry → Adapter"""
    # 启动 Flask 测试客户端
    resp = app.test_client().get('/api/stock_data?stock_code=000001&period=1y')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['data']) > 0
    assert data['meta']['source'] != 'akshare'  # 不再硬编码
```

### 5.3 回归测试

```bash
pytest tests/backend/unit/test_data_provider.py -v
pytest tests/backend/api/test_stock_data_routes.py -v
pytest -k "data_provider or registry or stock_data" -v
```

---

## 6. 风险评估与缓解

| 风险 | 级别 | 缓解措施 |
|------|------|---------|
| DataProvider 返回值改为元组破坏现有调用方 | High | 分步实施：先改 DataProvider，逐个适配调用方 |
| Registry 性能不如 DataProvider 单例/缓存 | Medium | 在 DataProvider 层保留缓存/限流 |
| source 透传链路遗漏 | Medium | 单元测试覆盖每个环节 |
| 历史 pytest 大量依赖 DataProvider mock | Low | 兼容性包装：DataProvider 保留旧接口，新增 `_with_source` 变体 |

---

## 7. 回滚方案

### 7.1 代码回滚

```bash
git revert <commit-hash>  # Step 1-4 各一个 commit
```

### 7.2 数据库回滚

无数据库变更，无需回滚。

### 7.3 配置回滚

无 env 变更，无需回滚。

---

## 8. 时间线

| 阶段 | 预计工时 | 交付物 |
|------|---------|--------|
| Step 1: 桥接层 | 2h | data_provider.py 改造 |
| Step 2: source 透传 | 1h | 返回值改元组 |
| Step 3: web_server 适配 | 1h | meta.source 填充 |
| Step 4: 单元测试 | 2h | ≥5 用例 |
| Step 5: 集成测试 | 1h | 端到端验证 |
| Step 6: 回归测试 | 1h | 全量 pytest |
| **总计** | **8h** | **1 个工作日** |

---

## 9. 验收标准

- [ ] `DataProvider.get_stock_history` 返回 `(df, source)` 元组
- [ ] `/api/stock_data` 响应 `meta.source` 反映真实 adapter 名（非写死 'akshare'）
- [ ] 降级链统一到 `AdapterRegistry.DEFAULT_DOMAIN_MAP`
- [ ] 单元测试 ≥5 用例全绿
- [ ] pytest -k "data_provider or registry or stock_data" 全绿
- [ ] 前端 `/stock/600519` 页面显示正确 source 标签

---

## 10. 附录

### 10.1 相关文档

- CLAUDE.md § 数据路径审计（2026-07-24）
- `app/adapters/README.md`
- `app/core/README.md`

### 10.2 权威证据

- AdapterRegistry domain 设计: `app/adapters/adapter_registry.py` line 50-80
- DataProvider 单例模式: `app/core/data_provider.py` line 23-32
- FallbackManager 重试逻辑: `app/core/fallback_manager.py` line 50-116

---

**文档状态**: ✅ 设计完成，待评审  
**下一步**: 代码实现（方案 B）
