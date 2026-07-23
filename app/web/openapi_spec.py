# Input: 无（静态 spec dict）
# Output: OpenAPI 3.0 JSON-serializable dict（暴露给 /api/openapi.json）
# Pos: API 文档自动生成层，维护核心路由 schema 契约
# 一旦被修改，请更新本头部注释，以及 app/web/README.md
"""
OpenAPI 3.0 Spec（S3-C3 Hunt5-Major 2026-05-20，S3-O/P1 第一/二批覆盖补齐）

手动维护核心路由的 OpenAPI 3.0 schema。
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
        'MarketStreamEvent': {
            'type': 'object',
            'description': (
                'SSE 单条事件 data 负载（市场指数实时流）。每条事件形如 '
                '`data: {json}\\n\\n`，json 即本 schema 描述的对象。'
            ),
            'properties': {
                'indices': {
                    'type': 'array',
                    'description': '主要市场指数实时快照（上证/深证/创业板/沪深300）',
                    'items': {'$ref': '#/components/schemas/MarketIndex'},
                },
                'source': {'type': 'string', 'example': 'eastmoney'},
            },
            # 实时流字段随上游数据源动态扩展，保守用 additionalProperties 兜底，不写死动态契约
            'additionalProperties': True,
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
        'GenericObject': {
            'type': 'object',
            'additionalProperties': True,
        },
        'McpCallRequest': {
            'type': 'object',
            'properties': {
                'tool': {'type': 'string'},
                'arguments': {
                    'type': 'object',
                    'additionalProperties': True,
                },
            },
            'required': ['tool'],
        },
        'McpCallResponse': {
            'type': 'object',
            'properties': {
                'result': {
                    'oneOf': [
                        {'$ref': '#/components/schemas/GenericObject'},
                        {'type': 'object', 'additionalProperties': True},
                    ],
                },
            },
            'additionalProperties': True,
        },
        'MetricsResponse': {
            'type': 'object',
            'additionalProperties': True,
        },
        'HealthDeepResponse': {
            'type': 'object',
            'properties': {
                'status': {'type': 'string'},
                'uptime_s': {'type': 'number'},
                'version': {'type': 'string'},
                'checks': {
                    'type': 'object',
                    'additionalProperties': True,
                },
                'elapsed_ms': {'type': 'number'},
            },
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
    '/api/health/deep': {
        'get': {
            'tags': ['System'],
            'summary': '深度健康检查',
            'operationId': 'getHealthDeep',
            'security': [],
            'responses': {
                '200': {
                    'description': '深度健康状态',
                    'content': {'application/json': {'schema': {
                        '$ref': '#/components/schemas/HealthDeepResponse',
                    }}},
                },
            },
        },
    },
    '/api/metrics': {
        'get': {
            'tags': ['System'],
            'summary': '基础运行指标',
            'operationId': 'getMetrics',
            'security': [],
            'responses': {
                '200': {
                    'description': '运行指标',
                    'content': {'application/json': {'schema': {
                        '$ref': '#/components/schemas/MetricsResponse',
                    }}},
                },
            },
        },
    },
    '/api/mcp/tools': {
        'get': {
            'tags': ['MCP'],
            'summary': '列出 MCP 工具',
            'operationId': 'listMcpTools',
            'responses': {
                '200': {
                    'description': 'MCP 工具列表',
                    'content': {'application/json': {'schema': {
                        '$ref': '#/components/schemas/GenericObject',
                    }}},
                },
            },
        },
    },
    '/api/mcp/call': {
        'post': {
            'tags': ['MCP'],
            'summary': '调用 MCP 工具',
            'operationId': 'callMcpTool',
            'requestBody': {
                'required': True,
                'content': {'application/json': {'schema': {
                    '$ref': '#/components/schemas/McpCallRequest',
                }}},
            },
            'responses': {
                '200': {
                    'description': 'MCP 调用结果',
                    'content': {'application/json': {'schema': {
                        '$ref': '#/components/schemas/McpCallResponse',
                    }}},
                },
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/shipping/bdi': {
        'get': {
            'tags': ['Shipping'],
            'summary': '获取 BDI 航运指数',
            'operationId': 'getShippingBdi',
            'parameters': [
                {'name': 'days', 'in': 'query',
                 'schema': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 30}},
            ],
            'responses': {
                '200': {'description': 'BDI 数据', 'content': {'application/json': {'schema': {
                    '$ref': '#/components/schemas/GenericObject',
                }}}},
            },
        },
    },
    '/api/shipping/port/{port}': {
        'get': {
            'tags': ['Shipping'],
            'summary': '获取港口吞吐量数据',
            'operationId': 'getShippingPort',
            'parameters': [
                {'name': 'port', 'in': 'path', 'required': True,
                 'schema': {'type': 'string'}},
                {'name': 'period', 'in': 'query',
                 'schema': {'type': 'string', 'enum': ['daily', 'monthly', 'yearly'], 'default': 'monthly'}},
            ],
            'responses': {
                '200': {'description': '港口数据', 'content': {'application/json': {'schema': {
                    '$ref': '#/components/schemas/GenericObject',
                }}}},
            },
        },
    },
    '/api/esg/{ticker}': {
        'get': {
            'tags': ['ESG'],
            'summary': '获取 ESG 评分',
            'operationId': 'getEsgScore',
            'parameters': [
                {'name': 'ticker', 'in': 'path', 'required': True,
                 'schema': {'type': 'string'}},
                {'name': 'source', 'in': 'query',
                 'schema': {'type': 'string', 'maxLength': 32, 'default': 'synthetic'}},
            ],
            'responses': {
                '200': {'description': 'ESG 数据', 'content': {'application/json': {'schema': {
                    '$ref': '#/components/schemas/GenericObject',
                }}}},
            },
        },
    },
    '/api/corporate/search': {
        'get': {
            'tags': ['Corporate'],
            'summary': '企业搜索',
            'operationId': 'searchCorporate',
            'parameters': [
                {'name': 'q', 'in': 'query', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 100}},
                {'name': 'limit', 'in': 'query',
                 'schema': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 20}},
            ],
            'responses': {
                '200': {'description': '企业搜索结果', 'content': {'application/json': {'schema': {
                    '$ref': '#/components/schemas/GenericObject',
                }}}},
            },
        },
    },
    '/api/jobs/search': {
        'get': {
            'tags': ['Jobs'],
            'summary': '招聘岗位搜索',
            'operationId': 'searchJobs',
            'parameters': [
                {'name': 'q', 'in': 'query', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 100}},
                {'name': 'limit', 'in': 'query',
                 'schema': {'type': 'integer', 'minimum': 1, 'maximum': 200, 'default': 20}},
            ],
            'responses': {
                '200': {'description': '岗位搜索结果', 'content': {'application/json': {'schema': {
                    '$ref': '#/components/schemas/GenericObject',
                }}}},
            },
        },
    },
    '/api/jobs/company/{company}': {
        'get': {
            'tags': ['Jobs'],
            'summary': '按公司获取招聘岗位',
            'operationId': 'getJobsByCompany',
            'parameters': [
                {'name': 'company', 'in': 'path', 'required': True,
                 'schema': {'type': 'string'}},
            ],
            'responses': {
                '200': {'description': '公司岗位数据', 'content': {'application/json': {'schema': {
                    '$ref': '#/components/schemas/GenericObject',
                }}}},
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
    '/api/market_stream': {
        'get': {
            'tags': ['Market'],
            'summary': '市场指数实时数据流（Server-Sent Events）',
            'operationId': 'streamMarketIndices',
            'description': (
                '持续的 Server-Sent Events 流，约每 10 秒推送一次市场主要指数实时快照。'
                '响应 Content-Type 为 `text/event-stream`，每条事件格式为 `data: {json}\\n\\n`，'
                '其中 json 为 MarketStreamEvent 对象。客户端应使用 EventSource（或等价 SSE 客户端）消费，'
                '连接保持长开直至客户端断开；上游异常时会推送 `{"indices": []}` 降级事件。'
            ),
            'responses': {
                '200': {
                    'description': 'SSE 事件流，每条 data 为一个 MarketStreamEvent JSON 对象',
                    'content': {
                        'text/event-stream': {
                            'schema': {'$ref': '#/components/schemas/MarketStreamEvent'},
                        },
                    },
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
    '/api/stock_name': {
        'get': {
            'tags': ['Stock'],
            'summary': '按股票代码查询股票名称',
            'operationId': 'getStockName',
            'parameters': [
                {'name': 'stock_code', 'in': 'query', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 20, 'example': '600519'}},
            ],
            'responses': {
                '200': {'description': '股票名称'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/stock_name_search': {
        'get': {
            'tags': ['Stock'],
            'summary': '按名称关键词反查股票代码',
            'operationId': 'searchStockName',
            'parameters': [
                {'name': 'q', 'in': 'query', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 20}},
                {'name': 'limit', 'in': 'query',
                 'schema': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 10}},
            ],
            'responses': {
                '200': {'description': '股票名称搜索结果'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/start_market_scan': {
        'post': {
            'tags': ['Scan'],
            'summary': '启动市场扫描任务',
            'operationId': 'startMarketScan',
            'requestBody': {
                'required': True,
                'content': {'application/json': {'schema': {
                    'type': 'object',
                    'properties': {
                        'stock_list': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 500},
                        'market_type': {'type': 'string', 'default': 'A'},
                        'min_score': {'type': 'number', 'minimum': 0, 'maximum': 100, 'default': 0},
                        'max_stocks': {'type': 'integer', 'minimum': 1, 'maximum': 500, 'default': 50},
                    },
                }}},
            },
            'responses': {
                '200': {'description': '任务已创建'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/scan_status/{task_id}': {
        'get': {
            'tags': ['Scan'],
            'summary': '获取市场扫描任务状态',
            'operationId': 'getScanStatus',
            'parameters': [
                {'name': 'task_id', 'in': 'path', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 64}},
            ],
            'responses': {
                '200': {'description': '任务状态'},
                '404': {'description': '任务不存在'},
            },
        },
    },
    '/api/cancel_scan/{task_id}': {
        'post': {
            'tags': ['Scan'],
            'summary': '取消市场扫描任务',
            'operationId': 'cancelScan',
            'parameters': [
                {'name': 'task_id', 'in': 'path', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 64}},
            ],
            'responses': {
                '200': {'description': '取消成功或任务已结束'},
                '404': {'description': '任务不存在'},
            },
        },
    },
    '/api/index_stocks': {
        'get': {
            'tags': ['Market'],
            'summary': '获取指数成分股',
            'operationId': 'getIndexStocks',
            'parameters': [
                {'name': 'index_code', 'in': 'query',
                 'schema': {'type': 'string', 'enum': ['000300', '000905', '000852', '000001'], 'default': '000300'}},
            ],
            'responses': {
                '200': {'description': '指数成分股列表'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/industry_stocks': {
        'get': {
            'tags': ['Industry'],
            'summary': '获取行业成分股',
            'operationId': 'getIndustryStocks',
            'parameters': [
                {'name': 'industry', 'in': 'query', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 50}},
            ],
            'responses': {
                '200': {'description': '行业成分股列表'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/board_stocks': {
        'get': {
            'tags': ['Market'],
            'summary': '获取板块股票列表',
            'operationId': 'getBoardStocks',
            'parameters': [
                {'name': 'board', 'in': 'query',
                 'schema': {'type': 'string',
                            'enum': ['hs300', 'zz500', 'zz1000', 'kc50', 'kc100', 'bj50'],
                            'default': 'hs300'}},
            ],
            'responses': {
                '200': {'description': '板块股票列表'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/concept_fund_flow': {
        'get': {
            'tags': ['FundFlow'],
            'summary': '获取概念资金流向',
            'operationId': 'getConceptFundFlow',
            'parameters': [
                {'name': 'period', 'in': 'query',
                 'schema': {'type': 'string', 'maxLength': 20, 'default': '10日排行'}},
            ],
            'responses': {
                '200': {'description': '概念资金流向数据'},
            },
        },
    },
    '/api/individual_fund_flow_rank': {
        'get': {
            'tags': ['FundFlow'],
            'summary': '获取个股资金流向排名',
            'operationId': 'getIndividualFundFlowRank',
            'parameters': [
                {'name': 'period', 'in': 'query',
                 'schema': {'type': 'string', 'maxLength': 20, 'default': '今日'}},
                {'name': 'market', 'in': 'query',
                 'schema': {'type': 'string', 'maxLength': 10, 'default': ''}},
            ],
            'responses': {
                '200': {'description': '个股资金流向排名'},
                '500': {'description': '数据源异常'},
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
    # ─────────────────────────────────────────────
    # S3-O/P1 第三批覆盖（2026-06-15）
    # ─────────────────────────────────────────────
    '/api/analysis_status/{task_id}': {
        'get': {
            'tags': ['Stock'],
            'summary': '获取个股分析任务状态',
            'operationId': 'getAnalysisStatus',
            'parameters': [
                {'name': 'task_id', 'in': 'path', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 64}},
            ],
            'responses': {
                '200': {'description': '任务状态'},
                '404': {'description': '任务不存在'},
            },
        },
    },
    '/api/cancel_analysis/{task_id}': {
        'post': {
            'tags': ['Stock'],
            'summary': '取消个股分析任务',
            'operationId': 'cancelAnalysis',
            'parameters': [
                {'name': 'task_id', 'in': 'path', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 64}},
            ],
            'responses': {
                '200': {'description': '取消成功或任务已结束'},
                '404': {'description': '任务不存在'},
            },
        },
    },
    '/api/enhanced_analysis': {
        'post': {
            'tags': ['Stock'],
            'summary': '启动增强分析',
            'operationId': 'enhancedAnalysis',
            'requestBody': {
                'required': True,
                'content': {'application/json': {'schema': {
                    'type': 'object',
                    'properties': {
                        'stock_code': {'type': 'string', 'minLength': 1, 'maxLength': 20},
                        'market_type': {'type': 'string', 'maxLength': 10, 'default': 'A'},
                        'research_depth': {'type': 'integer', 'minimum': 1, 'maximum': 5, 'default': 3},
                    },
                    'required': ['stock_code'],
                }}},
            },
            'responses': {
                '200': {'description': '分析结果或任务已创建'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/start_etf_analysis': {
        'post': {
            'tags': ['Stock'],
            'summary': '启动 ETF 分析任务',
            'operationId': 'startEtfAnalysis',
            'requestBody': {
                'required': True,
                'content': {'application/json': {'schema': {
                    'type': 'object',
                    'properties': {
                        'etf_code': {'type': 'string', 'minLength': 1, 'maxLength': 20},
                        'market_type': {'type': 'string', 'maxLength': 10, 'default': 'A'},
                        'research_depth': {'type': 'integer', 'minimum': 1, 'maximum': 5, 'default': 3},
                    },
                    'required': ['etf_code'],
                }}},
            },
            'responses': {
                '200': {'description': '任务已创建'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/etf_analysis_status/{task_id}': {
        'get': {
            'tags': ['Stock'],
            'summary': '获取 ETF 分析任务状态',
            'operationId': 'getEtfAnalysisStatus',
            'parameters': [
                {'name': 'task_id', 'in': 'path', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 64}},
            ],
            'responses': {
                '200': {'description': '任务状态'},
                '404': {'description': '任务不存在'},
            },
        },
    },
    '/api/sector_stocks': {
        'get': {
            'tags': ['Market'],
            'summary': '获取板块/行业成分股',
            'operationId': 'getSectorStocks',
            'parameters': [
                {'name': 'sector', 'in': 'query', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 50}},
            ],
            'responses': {
                '200': {'description': '板块成分股列表'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/individual_fund_flow': {
        'get': {
            'tags': ['FundFlow'],
            'summary': '获取个股资金流向',
            'operationId': 'getIndividualFundFlow',
            'parameters': [
                {'name': 'stock_code', 'in': 'query', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 20}},
                {'name': 'market_type', 'in': 'query',
                 'schema': {'type': 'string', 'maxLength': 10, 'default': ''}},
            ],
            'responses': {
                '200': {'description': '个股资金流向数据'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/stock_quote_batch': {
        'get': {
            'tags': ['Stock'],
            'summary': '批量获取股票实时报价',
            'operationId': 'getStockQuoteBatch',
            'parameters': [
                {'name': 'codes', 'in': 'query', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 2000},
                 'description': '逗号分隔的股票代码列表'},
                {'name': 'market_type', 'in': 'query',
                 'schema': {'type': 'string', 'enum': ['A', 'HK', 'US', 'B'], 'default': 'A'}},
                {'name': 'max_codes', 'in': 'query',
                 'schema': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 100}},
            ],
            'responses': {
                '200': {'description': '批量报价数据'},
                '400': {'description': '参数错误'},
            },
        },
    },
    # ─────────────────────────────────────────────
    # S3-O/P1 第四批覆盖（2026-06-15）
    # 基本面/资金/风险/场景/QA/指数/行业分析域
    # ─────────────────────────────────────────────
    '/api/fundamental_analysis': {
        'post': {
            'tags': ['Stock'],
            'summary': '基本面分析评分',
            'operationId': 'fundamentalAnalysis',
            'requestBody': {
                'required': True,
                'content': {'application/json': {'schema': {
                    'type': 'object',
                    'properties': {
                        'stock_code': {'type': 'string', 'minLength': 1, 'maxLength': 20},
                    },
                    'required': ['stock_code'],
                }}},
            },
            'responses': {
                '200': {'description': '基本面分析结果'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/capital_flow': {
        'post': {
            'tags': ['FundFlow'],
            'summary': '资金流向评分',
            'operationId': 'capitalFlow',
            'requestBody': {
                'required': True,
                'content': {'application/json': {'schema': {
                    'type': 'object',
                    'properties': {
                        'stock_code': {'type': 'string', 'minLength': 1, 'maxLength': 20},
                        'market_type': {'type': 'string', 'maxLength': 10, 'default': ''},
                    },
                    'required': ['stock_code'],
                }}},
            },
            'responses': {
                '200': {'description': '资金流向评分结果'},
                '400': {'description': '参数错误'},
                '503': {'description': '资金流向数据源不可用'},
            },
        },
    },
    '/api/scenario_predict': {
        'post': {
            'tags': ['Stock'],
            'summary': '情景预测',
            'operationId': 'scenarioPredict',
            'requestBody': {
                'required': True,
                'content': {'application/json': {'schema': {
                    'type': 'object',
                    'properties': {
                        'stock_code': {'type': 'string', 'minLength': 1, 'maxLength': 20},
                        'market_type': {'type': 'string', 'maxLength': 10, 'default': 'A'},
                        'days': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 60},
                    },
                    'required': ['stock_code'],
                }}},
            },
            'responses': {
                '200': {'description': '情景预测结果'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/qa': {
        'post': {
            'tags': ['Stock'],
            'summary': '智能问答',
            'operationId': 'stockQa',
            'requestBody': {
                'required': True,
                'content': {'application/json': {'schema': {
                    'type': 'object',
                    'properties': {
                        'stock_code': {'type': 'string', 'minLength': 1, 'maxLength': 20},
                        'question': {'type': 'string', 'minLength': 1, 'maxLength': 1000},
                        'market_type': {'type': 'string', 'maxLength': 10, 'default': 'A'},
                    },
                    'required': ['stock_code', 'question'],
                }}},
            },
            'responses': {
                '200': {'description': '智能问答结果'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/risk_analysis': {
        'post': {
            'tags': ['Stock'],
            'summary': '个股风险分析',
            'operationId': 'riskAnalysis',
            'requestBody': {
                'required': True,
                'content': {'application/json': {'schema': {
                    'type': 'object',
                    'properties': {
                        'stock_code': {'type': 'string', 'minLength': 1, 'maxLength': 20},
                        'market_type': {'type': 'string', 'maxLength': 10, 'default': 'A'},
                    },
                    'required': ['stock_code'],
                }}},
            },
            'responses': {
                '200': {'description': '风险分析结果'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/portfolio_risk': {
        'post': {
            'tags': ['Stock'],
            'summary': '投资组合风险分析',
            'description': (
                '加权组合风险 + Sprint3 诊断字段。'
                '响应保守追加 sector_concentration / name_overlap / defensive_weight / '
                'unknown_industry_share；缺行业=unknown，禁止假行业。'
            ),
            'operationId': 'portfolioRisk',
            'requestBody': {
                'required': True,
                'content': {'application/json': {'schema': {
                    'type': 'object',
                    'properties': {
                        'portfolio': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'additionalProperties': True,
                                'properties': {
                                    'stock_code': {'type': 'string'},
                                    'weight': {'type': 'number'},
                                    'market_type': {'type': 'string'},
                                    'industry': {
                                        'type': 'string',
                                        'description': '可选；缺省后端查询，查不到=unknown',
                                    },
                                    'stock_name': {'type': 'string'},
                                },
                            },
                            'minItems': 1,
                            'maxItems': 100,
                        },
                    },
                    'required': ['portfolio'],
                }}},
            },
            'responses': {
                '200': {
                    'description': (
                        '组合风险+诊断。追加 sector_concentration、name_overlap、'
                        'defensive_weight、unknown_industry_share 等；其余字段可扩展。'
                    ),
                },
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/index_analysis': {
        'get': {
            'tags': ['Market'],
            'summary': '指数分析',
            'operationId': 'indexAnalysis',
            'parameters': [
                {'name': 'index_code', 'in': 'query', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 20}},
                {'name': 'limit', 'in': 'query',
                 'schema': {'type': 'integer', 'minimum': 1, 'maximum': 500, 'default': 30}},
            ],
            'responses': {
                '200': {'description': '指数分析结果'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/industry_analysis': {
        'get': {
            'tags': ['Industry'],
            'summary': '行业分析',
            'operationId': 'industryAnalysis',
            'parameters': [
                {'name': 'industry', 'in': 'query', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 50}},
                {'name': 'limit', 'in': 'query',
                 'schema': {'type': 'integer', 'minimum': 1, 'maximum': 500, 'default': 30}},
            ],
            'responses': {
                '200': {'description': '行业分析结果'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/industry_fund_flow': {
        'get': {
            'tags': ['Industry'],
            'summary': '行业资金流向',
            'operationId': 'industryFundFlow',
            'parameters': [
                {'name': 'symbol', 'in': 'query',
                 'schema': {'type': 'string', 'maxLength': 20, 'default': '即时'}},
            ],
            'responses': {
                '200': {'description': '行业资金流向数据'},
            },
        },
    },
    '/api/industry_detail': {
        'get': {
            'tags': ['Industry'],
            'summary': '行业详细信息',
            'operationId': 'industryDetail',
            'parameters': [
                {'name': 'industry', 'in': 'query', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 50}},
            ],
            'responses': {
                '200': {'description': '行业详细信息'},
                '400': {'description': '参数错误'},
                '404': {'description': '未找到行业'},
            },
        },
    },
    # ─────────────────────────────────────────────
    # S3-O/P1 第六批（最终批）覆盖（2026-06-15）
    # P3 另类数据 + 运维 + AI 分析域
    # ─────────────────────────────────────────────
    '/api/ai/agent-analyze': {
        'post': {
            'tags': ['Agent'],
            'summary': 'AI 智能体分析',
            'operationId': 'aiAgentAnalyze',
            'requestBody': {
                'required': True,
                'content': {'application/json': {'schema': {
                    'type': 'object',
                    'properties': {
                        'stock_code': {'type': 'string', 'minLength': 1, 'maxLength': 20},
                        'market_type': {'type': 'string', 'maxLength': 10, 'default': 'A'},
                        'research_depth': {'type': 'integer', 'minimum': 1, 'maximum': 5, 'default': 3},
                        'conversation_id': {'type': 'string', 'maxLength': 100, 'default': ''},
                        'user_message': {'type': 'string', 'maxLength': 5000, 'default': ''},
                        'message': {'type': 'string', 'maxLength': 5000, 'default': ''},
                    },
                    'required': ['stock_code'],
                }}},
            },
            'responses': {
                '200': {'description': 'AI 智能体分析结果'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/esg/climate/{cik}': {
        'get': {
            'tags': ['ESG'],
            'summary': 'EDGAR 气候披露',
            'operationId': 'esgClimate',
            'parameters': [
                {'name': 'cik', 'in': 'path', 'required': True,
                 'schema': {'type': 'string'}},
            ],
            'responses': {
                '200': {'description': '气候披露数据'},
                '400': {'description': 'cik 不能为空'},
            },
        },
    },
    '/api/corporate/{company_id}/network': {
        'get': {
            'tags': ['Corporate'],
            'summary': '企业关系网络',
            'operationId': 'corporateNetwork',
            'parameters': [
                {'name': 'company_id', 'in': 'path', 'required': True,
                 'description': '允许内含斜杠（如 us_ca/SAMPLEID）',
                 'schema': {'type': 'string'}},
            ],
            'responses': {
                '200': {'description': '企业关系网络数据'},
                '400': {'description': 'company_id 非法'},
            },
        },
    },
    '/api/satellite/search': {
        'get': {
            'tags': ['Satellite'],
            'summary': '卫星另类数据检索',
            'operationId': 'satelliteSearch',
            'parameters': [
                {'name': 'q', 'in': 'query', 'required': True,
                 'schema': {'type': 'string', 'minLength': 1, 'maxLength': 200}},
            ],
            'responses': {
                '200': {'description': '卫星数据检索结果'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/alt_data/{ticker}': {
        'get': {
            'tags': ['AltData'],
            'summary': '聚合另类数据（shipping/esg/hiring/corporate）',
            'operationId': 'altData',
            'parameters': [
                {'name': 'ticker', 'in': 'path', 'required': True,
                 'schema': {'type': 'string', 'maxLength': 20}},
            ],
            'responses': {
                '200': {'description': '聚合另类数据结果（部分失败不阻断）'},
                '400': {'description': '参数错误'},
            },
        },
    },
    '/api/adapters/status': {
        'get': {
            'tags': ['Ops'],
            'summary': '数据源适配器健康状态',
            'operationId': 'adaptersStatus',
            'responses': {
                '200': {'description': '各适配器健康状态'},
            },
        },
    },
    '/api/registry/stats': {
        'get': {
            'tags': ['Ops'],
            'summary': '适配器注册表统计',
            'operationId': 'registryStats',
            'responses': {
                '200': {'description': '注册表统计信息'},
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
    # ── 第五批（补做）：行业对比 / 历史分析 / 新闻 / Agent 状态与审批 / AI 对话 ──
    '/api/industry_compare': {
        'get': {
            'tags': ['Industry'],
            'summary': '行业横向对比',
            'operationId': 'getIndustryCompare',
            'parameters': [
                {'name': 'limit', 'in': 'query',
                 'schema': {'type': 'integer', 'default': 10, 'minimum': 1, 'maximum': 500}},
            ],
            'responses': {
                '200': {'description': '行业对比结果',
                        'content': {'application/json': {'schema': {'$ref': '#/components/schemas/GenericObject'}}}},
            },
        },
    },
    '/api/history_analysis': {
        'get': {
            'tags': ['Stock'],
            'summary': '历史分析记录',
            'operationId': 'getHistoryAnalysis',
            'parameters': [
                {'name': 'stock_code', 'in': 'query', 'required': True,
                 'schema': {'type': 'string', 'example': '600519'}},
                {'name': 'limit', 'in': 'query',
                 'schema': {'type': 'integer', 'default': 10, 'minimum': 1, 'maximum': 500}},
            ],
            'responses': {
                '200': {'description': '历史分析列表',
                        'content': {'application/json': {'schema': {'$ref': '#/components/schemas/GenericObject'}}}},
                '400': {'description': '参数校验失败'},
            },
        },
    },
    '/api/latest_news': {
        'get': {
            'tags': ['News'],
            'summary': '最新财经新闻',
            'operationId': 'getLatestNews',
            'parameters': [
                {'name': 'days', 'in': 'query',
                 'schema': {'type': 'integer', 'default': 1, 'minimum': 1, 'maximum': 30}},
                {'name': 'limit', 'in': 'query',
                 'schema': {'type': 'integer', 'default': 500, 'minimum': 1, 'maximum': 500}},
                {'name': 'important', 'in': 'query',
                 'schema': {'type': 'string', 'default': '0', 'enum': ['0', '1']}},
                {'name': 'type', 'in': 'query',
                 'schema': {'type': 'string', 'default': 'all', 'enum': ['all', 'hotspot']}},
            ],
            'responses': {
                '200': {'description': '新闻列表',
                        'content': {'application/json': {'schema': {'$ref': '#/components/schemas/GenericObject'}}}},
            },
        },
    },
    '/api/news_sentiment': {
        'get': {
            'tags': ['News'],
            'summary': '新闻情绪分析',
            'operationId': 'getNewsSentiment',
            'parameters': [
                {'name': 'days', 'in': 'query',
                 'schema': {'type': 'integer', 'default': 1, 'minimum': 1, 'maximum': 30}},
            ],
            'responses': {
                '200': {'description': '新闻情绪结果',
                        'content': {'application/json': {'schema': {'$ref': '#/components/schemas/GenericObject'}}}},
            },
        },
    },
    '/api/agent_analysis_status/{task_id}': {
        'get': {
            'tags': ['Agent'],
            'summary': '查询智能体分析任务状态',
            'operationId': 'getAgentAnalysisStatus',
            'parameters': [
                {'name': 'task_id', 'in': 'path', 'required': True,
                 'schema': {'type': 'string'}},
            ],
            'responses': {
                '200': {'description': '任务状态',
                        'content': {'application/json': {'schema': {'$ref': '#/components/schemas/GenericObject'}}}},
                '404': {'description': '任务不存在'},
            },
        },
    },
    '/api/delete_agent_analysis': {
        'post': {
            'tags': ['Agent'],
            'summary': '批量删除智能体分析记录',
            'operationId': 'deleteAgentAnalysis',
            'requestBody': {
                'required': True,
                'content': {'application/json': {'schema': {
                    'type': 'object',
                    'required': ['task_ids'],
                    'properties': {
                        'task_ids': {
                            'type': 'array',
                            'items': {'type': 'string', 'minLength': 1, 'maxLength': 100},
                            'minItems': 1, 'maxItems': 200,
                        },
                    },
                }}},
            },
            'responses': {
                '200': {'description': '删除结果',
                        'content': {'application/json': {'schema': {'$ref': '#/components/schemas/GenericObject'}}}},
                '400': {'description': '参数校验失败'},
            },
        },
    },
    '/api/agent_pending_approvals': {
        'get': {
            'tags': ['Agent'],
            'summary': '列出待审批的智能体任务',
            'operationId': 'getAgentPendingApprovals',
            'responses': {
                '200': {'description': '待审批任务列表',
                        'content': {'application/json': {'schema': {'$ref': '#/components/schemas/GenericObject'}}}},
            },
        },
    },
    '/api/agent_submit_approval': {
        'post': {
            'tags': ['Agent'],
            'summary': '提交智能体任务审批结果',
            'operationId': 'submitAgentApproval',
            'requestBody': {
                'required': True,
                'content': {'application/json': {'schema': {
                    'type': 'object',
                    'required': ['task_id'],
                    'properties': {
                        'task_id': {'type': 'string', 'minLength': 1, 'maxLength': 100},
                        'approved': {'type': 'boolean', 'default': False},
                        'feedback': {'type': 'string', 'default': '', 'maxLength': 2000},
                    },
                }}},
            },
            'responses': {
                '200': {'description': '审批提交结果',
                        'content': {'application/json': {'schema': {'$ref': '#/components/schemas/GenericObject'}}}},
                '400': {'description': '参数校验失败'},
            },
        },
    },
    '/api/ai/chat': {
        'post': {
            'tags': ['AI'],
            'summary': 'AI 对话（SSE 流式；Sprint2 意图 meta + 可选真仓 portfolio_snapshot）',
            'operationId': 'postAiChat',
            'requestBody': {
                'required': True,
                'content': {'application/json': {'schema': {
                    'type': 'object',
                    'required': ['message'],
                    'properties': {
                        'message': {'type': 'string', 'minLength': 1, 'maxLength': 5000},
                        'conversation_id': {'type': 'string', 'default': '', 'maxLength': 100},
                        'stock_code': {'type': 'string', 'default': '', 'maxLength': 20},
                        'market_type': {'type': 'string', 'default': 'A', 'maxLength': 10},
                        'research_depth': {'type': 'integer', 'default': 3, 'minimum': 1, 'maximum': 5},
                        'portfolio_snapshot': {
                            'type': 'object',
                            'description': (
                                'Sprint2 可选真仓快照（前端 portfolio-store）；'
                                'holdings 可空；服务端禁止编造持仓。'
                                'SSE 先推 event:meta 含 intent 分类。'
                            ),
                            'additionalProperties': True,
                            'properties': {
                                'holdings': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'object',
                                        'properties': {
                                            'code': {'type': 'string'},
                                            'name': {'type': 'string'},
                                            'weight': {'type': 'number'},
                                            'shares': {'type': 'number'},
                                            'cost': {'type': 'number'},
                                            'market_type': {'type': 'string'},
                                        },
                                    },
                                },
                                'source': {'type': 'string'},
                                'as_of': {'type': 'string'},
                            },
                        },
                    },
                }}},
            },
            'responses': {
                '200': {'description': 'SSE 事件流（text/event-stream；含 meta/token/artifact/done）',
                        'content': {'text/event-stream': {'schema': {'type': 'string'}}}},
                '400': {'description': '参数校验失败'},
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
        {'name': 'Scan', 'description': '市场扫描任务'},
        {'name': 'Industry', 'description': '行业数据'},
        {'name': 'News', 'description': '财经新闻/情绪'},
        {'name': 'AI', 'description': 'AI 对话'},
        {'name': 'FundFlow', 'description': '资金流向'},
        {'name': 'MCP', 'description': 'MCP 工具'},
        {'name': 'Shipping', 'description': '航运另类数据'},
        {'name': 'ESG', 'description': 'ESG 另类数据'},
        {'name': 'Corporate', 'description': '企业网络另类数据'},
        {'name': 'Jobs', 'description': '招聘信号另类数据'},
        {'name': 'Satellite', 'description': '卫星另类数据'},
        {'name': 'AltData', 'description': '聚合另类数据'},
        {'name': 'Ops', 'description': '运维/适配器注册表'},
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
