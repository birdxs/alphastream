# Input: 无（静态 spec dict）
# Output: OpenAPI 3.0 JSON-serializable dict（暴露给 /api/openapi.json）
# Pos: API 文档自动生成层，维护核心路由 schema 契约
# 一旦被修改，请更新本头部注释，以及 app/web/README.md
"""
OpenAPI 3.0 Spec（S3-C3 Hunt5-Major 2026-05-20）

手动维护 10 个核心路由的 OpenAPI 3.0 schema。
暴露为 /api/openapi.json 供 Swagger UI / 前端契约校验使用。
后续路由逐步通过 spec_add_path() 迁移注册。
"""
from __future__ import annotations
from typing import Dict, Any

# ─────────────────────────────────────────────
# Reusable component schemas
# ─────────────────────────────────────────────

_COMPONENTS: Dict[str, Any] = {
    'schemas': {
        'SuccessEnvelope': {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean', 'example': True},
                'data': {'type': 'object'},
            },
            'required': ['success'],
        },
        'ErrorEnvelope': {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean', 'example': False},
                'error_code': {'type': 'string', 'example': 'INVALID_INPUT'},
                'message': {'type': 'string'},
            },
            'required': ['success', 'error_code', 'message'],
        },
        'MarketIndex': {
            'type': 'object',
            'properties': {
                'code': {'type': 'string', 'example': '000001'},
                'name': {'type': 'string', 'example': '上证指数'},
                'price': {'type': 'number', 'format': 'float'},
                'change_pct': {'type': 'number', 'format': 'float'},
                'volume': {'type': 'number'},
                'timestamp': {'type': 'string', 'format': 'date-time'},
            },
        },
        'ConversationSummary': {
            'type': 'object',
            'properties': {
                'conversation_id': {'type': 'string'},
                'title': {'type': 'string'},
                'created_at': {'type': 'string'},
                'updated_at': {'type': 'string'},
                'message_count': {'type': 'integer'},
                'stock_codes': {'type': 'array', 'items': {'type': 'string'}},
            },
        },
        'CursorPage': {
            'type': 'object',
            'properties': {
                'items': {'type': 'array', 'items': {'type': 'object'}},
                'next_cursor': {'type': 'string', 'nullable': True},
                'limit': {'type': 'integer'},
            },
            'required': ['items', 'next_cursor', 'limit'],
        },
    },
    'securitySchemes': {
        'ApiKeyAuth': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'X-API-Key',
        },
    },
}

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────

_PATHS: Dict[str, Any] = {
    '/api/health': {
        'get': {
            'tags': ['System'],
            'summary': '健康检查',
            'operationId': 'getHealth',
            'security': [],
            'responses': {
                '200': {
                    'description': '服务正常',
                    'content': {'application/json': {'schema': {
                        'type': 'object',
                        'properties': {
                            'status': {'type': 'string', 'example': 'ok'},
                            'uptime_s': {'type': 'number'},
                        },
                    }}},
                },
            },
        },
    },
    '/api/market_indices': {
        'get': {
            'tags': ['Market'],
            'summary': '获取市场主要指数（上证/深证/创业板/沪深300）',
            'operationId': 'getMarketIndices',
            'parameters': [
                {
                    'name': 'refresh',
                    'in': 'query',
                    'schema': {'type': 'boolean', 'default': False},
                    'description': '强制刷新缓存',
                },
            ],
            'responses': {
                '200': {
                    'description': '指数数据',
                    'content': {'application/json': {'schema': {
                        'type': 'object',
                        'properties': {
                            'indices': {
                                'type': 'array',
                                'items': {'$ref': '#/components/schemas/MarketIndex'},
                            },
                            'source': {'type': 'string', 'example': 'eastmoney'},
                            'cache': {'type': 'string', 'example': 'HIT'},
                        },
                    }}},
                },
            },
        },
    },
    '/api/stock_data': {
        'get': {
            'tags': ['Stock'],
            'summary': 'K 线历史数据',
            'operationId': 'getStockData',
            'parameters': [
                {'name': 'stock_code', 'in': 'query', 'required': True,
                 'schema': {'type': 'string', 'example': '600519'}},
                {'name': 'period', 'in': 'query',
                 'schema': {'type': 'string', 'default': 'daily',
                            'enum': ['daily', 'weekly', 'monthly', 'min5', 'min15', 'min30', 'min60']}},
                {'name': 'start_date', 'in': 'query',
                 'schema': {'type': 'string', 'pattern': r'^\d{8}$', 'example': '20240101'}},
                {'name': 'end_date', 'in': 'query',
                 'schema': {'type': 'string', 'pattern': r'^\d{8}$', 'example': '20241231'}},
                {'name': 'limit', 'in': 'query',
                 'schema': {'type': 'integer', 'default': 200, 'minimum': 1, 'maximum': 2000}},
            ],
            'responses': {
                '200': {'description': 'K 线数据列表'},
                '400': {'description': '参数错误', 'content': {'application/json': {
                    'schema': {'$ref': '#/components/schemas/ErrorEnvelope'}}}},
            },
        },
    },
    '/api/stock_profile': {
        'get': {
            'tags': ['Stock'],
            'summary': '股票基本面数据（PE/PB/ROE/市值/行业）',
            'operationId': 'getStockProfile',
            'parameters': [
                {'name': 'stock_code', 'in': 'query', 'required': True,
                 'schema': {'type': 'string', 'example': '600519'}},
            ],
            'responses': {
                '200': {'description': '基本面数据'},
                '400': {'description': '参数错误'},
                '503': {'description': '数据源超时'},
            },
        },
    },
    '/api/conversations': {
        'get': {
            'tags': ['Conversation'],
            'summary': '获取对话历史列表（cursor 分页）',
            'operationId': 'listConversations',
            'parameters': [
                {'name': 'cursor', 'in': 'query', 'schema': {'type': 'string'},
                 'description': '分页游标（上次响应的 next_cursor），省略表示从最新开始'},
                {'name': 'limit', 'in': 'query',
                 'schema': {'type': 'integer', 'default': 20, 'minimum': 1, 'maximum': 200}},
                {'name': 'offset', 'in': 'query',
                 'schema': {'type': 'integer'},
                 'deprecated': True,
                 'description': '已废弃，请使用 cursor'},
            ],
            'responses': {
                '200': {
                    'description': '对话列表（cursor 分页）',
                    'headers': {
                        'Deprecation': {
                            'schema': {'type': 'string'},
                            'description': '若使用 offset 参数，此 header 会返回废弃警告',
                        },
                    },
                    'content': {'application/json': {'schema': {
                        'allOf': [
                            {'$ref': '#/components/schemas/CursorPage'},
                            {'properties': {
                                'items': {
                                    'type': 'array',
                                    'items': {'$ref': '#/components/schemas/ConversationSummary'},
                                },
                            }},
                        ],
                    }}},
                },
            },
        },
    },
    '/api/conversations/{conversation_id}': {
        'get': {
            'tags': ['Conversation'],
            'summary': '获取单个对话详情',
            'operationId': 'getConversation',
            'parameters': [
                {'name': 'conversation_id', 'in': 'path', 'required': True,
                 'schema': {'type': 'string'}},
            ],
            'responses': {
                '200': {'description': '对话详情（含完整消息）'},
                '404': {'description': '对话不存在'},
            },
        },
        'delete': {
            'tags': ['Conversation'],
            'summary': '删除对话',
            'operationId': 'deleteConversation',
            'parameters': [
                {'name': 'conversation_id', 'in': 'path', 'required': True,
                 'schema': {'type': 'string'}},
            ],
            'responses': {
                '200': {'description': '删除成功'},
                '404': {'description': '对话不存在'},
            },
        },
    },
    '/api/agent_analysis_history': {
        'get': {
            'tags': ['Agent'],
            'summary': '获取智能体分析任务历史（cursor 分页）',
            'operationId': 'getAgentAnalysisHistory',
            'parameters': [
                {'name': 'cursor', 'in': 'query', 'schema': {'type': 'string'},
                 'description': '分页游标'},
                {'name': 'limit', 'in': 'query',
                 'schema': {'type': 'integer', 'default': 20, 'minimum': 1, 'maximum': 200}},
            ],
            'responses': {
                '200': {'description': '历史任务 cursor 分页'},
            },
        },
    },
    '/api/active_tasks': {
        'get': {
            'tags': ['Agent'],
            'summary': '获取正在进行的智能体分析任务',
            'operationId': 'getActiveTasks',
            'responses': {
                '200': {'description': '活跃任务列表'},
            },
        },
    },
    '/api/csrf_token': {
        'get': {
            'tags': ['Security'],
            'summary': '获取 CSRF Token',
            'operationId': 'getCsrfToken',
            'security': [],
            'responses': {
                '200': {'description': 'CSRF Token',
                        'content': {'application/json': {'schema': {
                            'type': 'object',
                            'properties': {'csrf_token': {'type': 'string'}},
                        }}}},
            },
        },
    },
    '/api/openapi.json': {
        'get': {
            'tags': ['System'],
            'summary': 'OpenAPI 3.0 spec（本文档）',
            'operationId': 'getOpenApiSpec',
            'security': [],
            'responses': {
                '200': {'description': 'OpenAPI 3.0 JSON'},
            },
        },
    },
}

# ─────────────────────────────────────────────
# 公共 spec dict
# ─────────────────────────────────────────────

OPENAPI_SPEC: Dict[str, Any] = {
    'openapi': '3.0.3',
    'info': {
        'title': 'StockAnal API',
        'version': '1.0.0',
        'description': (
            'StockAnal_Sys 后端 REST API。'
            '支持 X-API-Key header 鉴权（AUTH_REQUIRED=true 时必须携带）。'
        ),
    },
    'servers': [
        {'url': 'http://127.0.0.1:8888', 'description': '本地开发'},
    ],
    'security': [{'ApiKeyAuth': []}],
    'tags': [
        {'name': 'System', 'description': '系统/健康'},
        {'name': 'Market', 'description': '市场指数'},
        {'name': 'Stock', 'description': '股票数据'},
        {'name': 'Conversation', 'description': '对话历史'},
        {'name': 'Agent', 'description': '智能体分析'},
        {'name': 'Security', 'description': '鉴权/CSRF'},
    ],
    'paths': _PATHS,
    'components': _COMPONENTS,
}


def spec_add_path(path: str, method: str, operation: Dict[str, Any]) -> None:
    """运行时注册额外路由 spec（供后续路由迁移使用）。

    Args:
        path: OpenAPI path，如 '/api/new_endpoint'
        method: HTTP 方法小写，如 'get'
        operation: OpenAPI Operation Object dict
    """
    if path not in OPENAPI_SPEC['paths']:
        OPENAPI_SPEC['paths'][path] = {}
    OPENAPI_SPEC['paths'][path][method] = operation
