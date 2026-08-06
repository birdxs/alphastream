"""
[DP-P2-1] adapters/status 缓存测试
"""
import pytest
import time
from unittest.mock import patch


@pytest.fixture(autouse=True)
def clear_adapters_cache():
    """清理 adapters 缓存避免测试污染"""
    import app.web.web_server as ws
    if '_adapters_status_cache' in globals():
        globals()['_adapters_status_cache'] = None
    yield
    # 测试后清理
    if '_adapters_status_cache' in globals():
        globals()['_adapters_status_cache'] = None


class TestAdaptersStatusCache:
    """adapters/status 缓存机制测试"""

    def test_cache_hit(self, flask_client, monkeypatch):
        """缓存命中"""
        monkeypatch.setenv('ADAPTERS_STATUS_CACHE_TTL', '60')

        def mock_hc(cls_name, mod_path, timeout):
            return {"ok": True, "latency_ms": 10, "status": "ok"}

        with patch('app.web.web_server._hc_one', side_effect=mock_hc):
            # 首次请求 - 缓存 MISS
            resp1 = flask_client.get('/api/adapters/status')
            assert resp1.status_code == 200
            assert resp1.headers.get('X-Cache') == 'MISS'

            # 第二次请求 - 缓存 HIT（在 TTL 内）
            resp2 = flask_client.get('/api/adapters/status')
            assert resp2.status_code == 200
            assert resp2.headers.get('X-Cache') == 'HIT'
            assert 'X-Cache-Age' in resp2.headers

    def test_cache_expired(self, flask_client, monkeypatch):
        """缓存过期重新检查"""
        monkeypatch.setenv('ADAPTERS_STATUS_CACHE_TTL', '1')  # 1 秒 TTL

        def mock_hc(cls_name, mod_path, timeout):
            return {"ok": True, "latency_ms": 10, "status": "ok"}

        with patch('app.web.web_server._hc_one', side_effect=mock_hc):
            # 首次请求
            resp1 = flask_client.get('/api/adapters/status')
            assert resp1.status_code == 200
            assert resp1.headers.get('X-Cache') == 'MISS'

            # 等待缓存过期
            time.sleep(1.5)

            # 再次请求 - 应该重新检查
            resp2 = flask_client.get('/api/adapters/status')
            assert resp2.status_code == 200
            assert resp2.headers.get('X-Cache') == 'MISS'

    def test_cache_reduces_health_check_calls(self, flask_client, monkeypatch):
        """缓存减少健康检查调用次数"""
        monkeypatch.setenv('ADAPTERS_STATUS_CACHE_TTL', '60')
        call_count = {'count': 0}

        def mock_hc(cls_name, mod_path, timeout):
            call_count['count'] += 1
            return {"ok": True, "latency_ms": 10, "status": "ok"}

        with patch('app.web.web_server._hc_one', side_effect=mock_hc):
            # 首次请求
            flask_client.get('/api/adapters/status')
            first_count = call_count['count']
            assert first_count > 0  # 应该有调用

            # 第二次请求（缓存命中）
            flask_client.get('/api/adapters/status')
            second_count = call_count['count']
            assert second_count == first_count  # 不应该增加调用次数
