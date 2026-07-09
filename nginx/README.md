文件列表：default.conf、prod.conf、default.conf.template、prod.conf.template
地位：Nginx反向代理配置
功能：前后端分离部署的反向代理，SSE长连接支持，静态资源缓存，/api-docs兼容入口

## 模板渲染

template 文件使用环境变量占位符，部署时需渲染：

```bash
# 渲染 default.conf
export BACKEND_TIMEOUT=600
export BACKEND_CONNECT_TIMEOUT=10
envsubst < default.conf.template > default.conf

# 渲染 prod.conf
export BACKEND_TIMEOUT=600
export BACKEND_CONNECT_TIMEOUT=10
export FRONTEND_TIMEOUT=300
envsubst < prod.conf.template > prod.conf
```

环境变量说明：
- `BACKEND_TIMEOUT`：后端 API 读超时（秒），默认 600
- `BACKEND_CONNECT_TIMEOUT`：后端连接超时（秒），默认 10
- `FRONTEND_TIMEOUT`：前端读超时（秒），默认 300

一旦这里的结构发生变化，请务必更新我。
