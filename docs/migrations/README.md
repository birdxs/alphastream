# 数据库 Schema Migration 指南

## 版本控制机制

本项目使用 SQLite 内置 `PRAGMA user_version` 进行轻量级 schema 版本控制，无需引入 Alembic 等重型迁移框架。

---

## 当前版本

| 数据库文件 | Schema 版本 | 表结构 |
|---|---|---|
| `data/stock_analyzer.db` | **v1** | `stocks` / `analysis_results` / `industry_analysis` |
| `data/wind_cache.db` | **v1** | `wind_cache` / `wind_quota` |
| `data/agent_sessions/*.db` | **v1** | LangGraph 内置表（`checkpoints` / `writes` / `checkpoint_migrations`） |

---

## 版本变更记录

### v1（2026-07-09）

**初始版本**

- **业务库**（`data/stock_analyzer.db`）：
  - `stocks`: 股票基本信息
  - `analysis_results`: AI 分析结果
  - `industry_analysis`: 行业分析缓存

- **Wind 缓存**（`data/wind_cache.db`）：
  - `wind_cache`: Wind API 调用缓存（cache_key / payload_json / expires_at）
  - `wind_quota`: 日配额计数（day / used_s / used_a / used_b）

- **Agent 会话**（`data/agent_sessions/*.db`）：
  - LangGraph SqliteSaver 内置表（`checkpoints` / `writes` / `checkpoint_migrations`）
  - 索引：`ix_checkpoints_thread_id` / `ix_writes_thread_id`

---

## 迁移流程

### 检查当前版本

```bash
# 业务库
sqlite3 data/stock_analyzer.db "PRAGMA user_version"

# Wind 缓存
sqlite3 data/wind_cache.db "PRAGMA user_version"

# Agent 会话（示例）
sqlite3 data/agent_sessions/conv_abc123.db "PRAGMA user_version"
```

### 手动迁移示例（v1 → v2，未来版本占位）

```python
import sqlite3

def migrate_v1_to_v2(db_path: str):
    """示例：v1 → v2 迁移脚本。

    Args:
        db_path: 数据库文件路径（如 'data/wind_cache.db'）
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. 检查当前版本
    current_version = cursor.execute('PRAGMA user_version').fetchone()[0]
    if current_version != 1:
        raise RuntimeError(f"当前版本 {current_version} 不适合此脚本")

    # 2. 执行 schema 变更（示例）
    # cursor.execute('ALTER TABLE wind_cache ADD COLUMN metadata TEXT')

    # 3. 更新版本号
    cursor.execute('PRAGMA user_version = 2')

    conn.commit()
    conn.close()
    print(f"迁移完成: {db_path} → v2")

# 使用示例
# migrate_v1_to_v2('data/wind_cache.db')
```

### 启动时自动检查

代码会在启动时自动校验 schema 版本：
- **current == 0**（首次）：初始化为 target_version
- **current < target_version**：记录 warning，建议运行迁移脚本
- **current > target_version**：抛 RuntimeError，需升级代码或回退数据库
- **current == target_version**：正常运行

---

## 回滚策略

### 安全回滚（推荐）

```bash
# 1. 备份当前数据库
cp data/wind_cache.db data/wind_cache.db.backup

# 2. 回退版本号（示例：v2 → v1）
sqlite3 data/wind_cache.db "PRAGMA user_version = 1"

# 3. 如需反向 schema 变更，手动执行 SQL
# sqlite3 data/wind_cache.db "ALTER TABLE wind_cache DROP COLUMN metadata"
```

### 强制清空（破坏性）

```bash
# 删除数据库文件，下次启动自动重建为 v1
rm -f data/wind_cache.db data/wind_cache.db-wal data/wind_cache.db-shm
```

---

## 最佳实践

1. **版本升级前备份**：`cp *.db *.db.backup`
2. **迁移脚本幂等**：重复执行不破坏数据（`IF NOT EXISTS` / `IF NOT NULL`）
3. **保留旧版本数据**：不删除列/表，仅标记废弃（`is_deprecated` 字段）
4. **测试路径**：先在 dev 环境验证迁移脚本，再执行 prod
5. **监控日志**：启动后 grep `schema 版本` / `migration` 关键字

---

## 常见问题

### Q1：启动时报 "数据库版本过新"

```
RuntimeError: 数据库版本过新: v2 > v1，请升级代码或回退数据库版本
```

**原因**：数据库已被新版代码升级，旧代码无法识别。

**解决**：
- 升级代码到对应版本
- 或回退数据库版本（参考"回滚策略"）

### Q2：启动时报 "数据库版本过旧"

```
WARNING: 数据库 schema 版本过旧: v1 < v2，建议运行迁移脚本
```

**原因**：代码已升级，数据库未迁移。

**解决**：
- 根据日志提示的版本号，运行对应迁移脚本（如 `migrate_v1_to_v2.py`）
- 或手动执行 SQL 变更 + `PRAGMA user_version = 2`

### Q3：如何验证 schema 版本？

```bash
# 方法1：sqlite3 命令行
sqlite3 data/wind_cache.db "PRAGMA user_version"

# 方法2：Python
import sqlite3
conn = sqlite3.connect('data/wind_cache.db')
print(conn.execute('PRAGMA user_version').fetchone()[0])
conn.close()
```

---

## 相关文件

| 文件 | 作用 |
|---|---|
| `app/core/database.py` | 业务库 + schema 版本控制函数（`_init_schema_version`） |
| `app/core/wind_budget.py` | Wind 缓存库 + schema 版本控制调用 |
| `app/agents/coordinator.py` | LangGraph SqliteSaver（自带 `checkpoint_migrations` 表） |
| `docs/migrations/README.md` | 本文档 |

---

**最后更新**：2026-07-09（添加 v1 版本记录与迁移指南）
