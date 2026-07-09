文件列表：default.conf、prod.conf、default.conf.template、prod.conf.template
地位：Nginx反向代理配置
功能：前后端分离部署的反向代理，SSE长连接支持，静态资源缓存，/api-docs兼容入口

## 配置渲染

使用 `scripts/render_nginx_config.sh` 从模板生成配置：

```bash
# 使用默认值
./scripts/render_nginx_config.sh

# 自定义变量
BACKEND_TIMEOUT=900 FRONTEND_TIMEOUT=400 ./scripts/render_nginx_config.sh
```

**环境变量**（支持 `${VAR:-default}` 语法）：
- `BACKEND_TIMEOUT`：后端 API 读超时（秒），默认 600
- `BACKEND_CONNECT_TIMEOUT`：后端连接超时（秒），默认 10
- `FRONTEND_TIMEOUT`：前端读超时（秒），默认 300

**手动渲染**（不推荐）：
```bash
export BACKEND_TIMEOUT=600 BACKEND_CONNECT_TIMEOUT=10 FRONTEND_TIMEOUT=300
perl -pe 's/\$\{(\w+):-\d+\}/$ENV{$1}/ge' nginx/default.conf.template > nginx/default.conf
perl -pe 's/\$\{(\w+):-\d+\}/$ENV{$1}/ge' nginx/prod.conf.template > nginx/prod.conf
```

一旦这里的结构发生变化，请务必更新我。
