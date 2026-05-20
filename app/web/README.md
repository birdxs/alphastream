# app/web/ - Web服务模块
- web_server.py(路由+API), auth_middleware.py(认证), industry_api_endpoints.py(行业API)
- schema.py(marshmallow 路由 schema + @validate_schema 装饰器，S3-C4)
- openapi_spec.py(OpenAPI 3.0 spec dict + /api/openapi.json 端点，S3-C3)
- templates/(前端), static/(静态资源 含 swagger.json 2.0)
- 一旦这里的结构发生变化，请务必更新我... 就像重新标记领地一样。
