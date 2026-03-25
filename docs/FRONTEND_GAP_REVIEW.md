# 前端差异点评审报告（对标顶级金融产品）

## 评审时间: 2026-03-26
## 对标产品: Bloomberg Terminal / TradingView / Perplexity Finance / FinChat
## 评审人: 评审Agent（隶属香草少校团队）

## 差异点总计: 112个

---

### 维度1: 视觉设计品质 (12个)

| # | 差异点 | 当前状态 | 顶级标准 | 优先级 | 修复方案 |
|---|--------|---------|---------|--------|---------|
| 1 | 字体缺乏金融级等宽数字字体 | 仅使用Inter通用字体，`font-mono`回退到系统等宽字体 | Bloomberg使用专用金融数字字体(如Tabular Lining Figures)，TradingView使用`-tnum`特性 | P0 | 引入`font-variant-numeric: tabular-nums`全局应用于所有数字元素；或引入JetBrains Mono/IBM Plex Mono作为金融数字专用字体 |
| 2 | 暗色主题配色不够专业 | `globals.css`暗色用`oklch(0.13 0.015 250)`偏蓝黑色，但整体偏平淡 | Bloomberg Terminal经典深蓝黑(#1a1a2e)配高对比度橙/白；TradingView用#131722配精细层次 | P1 | 增加至少5级暗色层次（surface-0到surface-4），卡片边框增加微妙光泽，活跃元素增加辉光效果 |
| 3 | 品牌色缺乏金融行业辨识度 | primary使用shadcn默认黑白灰系，无品牌专属色 | Bloomberg橙+黑，TradingView蓝紫系，Robinhood绿色 | P1 | 定义品牌主色(建议深蓝#1e3a5f或金融蓝#2563eb)，建立完整色彩系统(primary/secondary/accent各5级) |
| 4 | 图标风格不统一 | 全部使用lucide-react纯线条图标，WelcomeScreen中混用emoji(机器人/图表等) | TradingView全自定义SVG图标系统；Bloomberg使用统一设计语言 | P1 | 建立图标设计规范：功能性图标统一用lucide-react，装饰性场景统一用自定义SVG或选定一套emoji风格，不混用 |
| 5 | 阴影/边框系统不精致 | Card组件使用shadcn默认边框，无分层阴影系统 | FinChat/Perplexity使用多层柔和阴影(shadow-sm到shadow-2xl)区分层级 | P1 | 定义elevation系统(0-5级)：卡片用elevation-1，弹窗用elevation-3，全屏用elevation-5，暗色模式用边框发光替代阴影 |
| 6 | 间距不遵循统一Grid系统 | 各组件间距混乱：p-3/p-4/p-6/py-1.5/py-2/py-2.5不一 | 顶级产品遵循严格的4px/8px Grid系统 | P1 | 建立spacing token系统(space-1=4px到space-12=48px)，全组件统一替换 |
| 7 | 渐变使用过度 | 头像用`bg-gradient-to-br from-blue-500 to-purple-600`，评分头部用渐变，风险/基本面评分都用渐变背景 | Bloomberg几乎不用渐变；TradingView仅在图表区域用微妙渐变 | P2 | 克制渐变使用：头像改为纯色+首字母；评分改用纯色背景+数字高亮；仅在图表填充区域使用渐变 |
| 8 | 导航栏缺乏层次和专业感 | Navbar仅一行高度14(56px)，纯文字+图标排列 | Bloomberg有多层工具栏；TradingView有搜索栏+市场选择+工具集成 | P1 | Navbar增加全局搜索输入框(Cmd+K触发)、当前关注股票快速切换、通知铃铛、用户头像 |
| 9 | 欢迎屏缺乏视觉冲击力 | WelcomeScreen用emoji图标+简单按钮列表 | Perplexity用精美插画+动态效果+分类卡片；Claude用简洁但精致的引导界面 | P2 | 重设计WelcomeScreen：用自定义SVG插画替代emoji，添加微动画，热门分析实时推荐，市场快讯轮播 |
| 10 | 对话侧边栏视觉过于简陋 | ConversationSidebar用纯文字列表，无分组/无搜索/无时间分组 | ChatGPT对话按日期分组(Today/Yesterday/Last 7 days)，支持搜索和文件夹 | P2 | 增加对话搜索、按日期分组（今天/昨天/上周/更早）、对话收藏/置顶、对话标签分类 |
| 11 | 全屏模式缺乏过渡动画 | ArtifactCard全屏模式直接切换`fixed inset-0`，无过渡效果 | TradingView图表全屏有平滑缩放过渡 | P2 | 添加全屏进入/退出的scale+fade过渡动画(framer-motion) |
| 12 | 消息气泡边角设计缺乏精致感 | 用户消息`rounded-br-md`，AI消息`rounded-bl-md`，但无尾巴形状 | iMessage/微信等专业聊天产品有气泡尾巴指向头像 | P2 | 添加CSS伪元素实现气泡尾巴，或采用Perplexity风格的无尾巴但更大圆角方案 |

---

### 维度2: 数据展示专业度 (12个)

| # | 差异点 | 当前状态 | 顶级标准 | 优先级 | 修复方案 |
|---|--------|---------|---------|--------|---------|
| 1 | 市场概览数据全部硬编码为0 | `market-overview.tsx`中indices初始化price=0/change=0，API调用仅请求news而非实际指数数据 | Bloomberg/同花顺实时推送指数数据，每秒刷新 | P0 | 对接后端市场指数API(GET /api/market_indices)，添加WebSocket或轮询(30s)实时更新 |
| 2 | 数字缺乏千分位格式化 | portfolio中`totalValue.toLocaleString()`仅部分使用，其他如价格目标`data.price_targets.support`直接渲染数字 | Wind/同花顺所有金融数字统一千分位+小数位格式(1,650.00) | P0 | 建立全局`formatNumber(value, decimals)`工具函数，所有金融数字统一格式化：价格保留2位小数+千分位，百分比保留2位，大数自动转万/亿 |
| 3 | 涨跌颜色使用不一致 | portfolio用硬编码`text-green-500/text-red-500`；capital-flow-chart用`upColor/downColor`；market-overview用`stock-up/stock-down`CSS类 | TradingView所有涨跌色来自统一配置，一处修改全局生效 | P0 | 统一所有涨跌颜色为CSS变量`var(--stock-up)/var(--stock-down)`，portfolio/所有组件不再硬编码green-500/red-500 |
| 4 | 百分比格式不统一 | portfolio用`toFixed(2)%`，有的有+号前缀有的没有 | 顶级金融产品统一格式：正数+2.50%，负数-1.30%，零0.00% | P0 | 建立`formatPercent(value)`函数，统一输出格式`+X.XX%`或`-X.XX%` |
| 5 | 表格缺乏专业金融样式 | StreamMarkdown中表格无斑马纹、无hover高亮、无排序 | Wind/同花顺表格有斑马纹、hover行高亮、点击列排序、固定表头 | P1 | Markdown表格组件增加`even:bg-muted/30`斑马纹、`hover:bg-accent/50`行高亮、数字列右对齐 |
| 6 | 数据更新无视觉反馈 | 市场数据/价格变化时无动画提示 | 同花顺价格变化时背景闪烁(红/绿闪)；Bloomberg有数字跳动动画 | P1 | 利用已有的`flash-up/flash-down`CSS类，在价格变化时触发闪烁动画；关键数字用`CountUp`动画 |
| 7 | 资金流数据单位换算不直观 | capital-flow-chart中`/10000`转万元显示，但tooltip无格式化 | 同花顺资金流用自动适配单位(万/亿)，tooltip有详细格式 | P1 | Tooltip自定义格式化：显示具体金额+单位(万/亿)，增加百分比占比 |
| 8 | 技术指标数值缺乏上下文参考 | RSI只显示数值如`65.3`，无高低区间标识 | TradingView的RSI有超买(>70)/超卖(<30)标识线和背景色区分 | P1 | RSI增加超买超卖颜色标识(>70红色,<30绿色)；MACD增加金叉/死叉图标；各指标增加简短解读文案 |
| 9 | 基本面指标缺乏行业对比 | fundamental-scorecard只展示单个股票指标，无行业平均/中位数对比 | FinChat展示指标时附带行业均值和排名百分位 | P2 | 每个指标旁增加行业均值参考线和百分位标签(如`PE 15.3x | 行业25.0x | 前30%`) |
| 10 | 新闻列表缺乏情绪热力值可视化 | news-feed仅用文字Badge标"利好/利空/中性" | Bloomberg新闻有情绪强度条(绿到红渐变条) | P2 | 情绪值改用微型进度条可视化(0-1范围，颜色渐变)，替代纯文字标签 |
| 11 | 投资者评分缺乏可视化对比 | investor-personas四位投资者用独立卡片，需逐个阅读 | FinChat用并排柱状图/雷达图直观对比多位分析师 | P2 | 增加四位投资者的并排对比柱状图(置信度/推荐)，一眼看清共识与分歧 |
| 12 | 数字精度不一致 | 价格有的保留0位`toFixed(0)`有的保留2位，volume无格式化 | 统一精度规范：价格2位、百分比2位、成交量自动单位(万手/亿) | P1 | 建立数字精度规范文档，全局统一应用 |

---

### 维度3: 交互细节 (11个)

| # | 差异点 | 当前状态 | 顶级标准 | 优先级 | 修复方案 |
|---|--------|---------|---------|--------|---------|
| 1 | 输入框无真正的自动增高 | `chat-input.tsx`的textarea设置`rows={1}`但无自动增高逻辑，仅CSS`minHeight/maxHeight`限制 | ChatGPT/Claude输入框随内容自动增高至最大高度后出滚动条 | P0 | 添加`useEffect`监听input变化，动态设置`textarea.style.height = textarea.scrollHeight + 'px'`，clamp在40px-120px |
| 2 | 无Cmd+K全局搜索 | 无全局搜索/命令面板快捷键 | Perplexity/Raycast/VS Code均支持Cmd+K全局搜索/命令 | P0 | 添加全局Cmd+K快捷键，弹出模态命令面板，支持搜索股票/切换页面/快捷命令 |
| 3 | 命令面板不支持键盘导航 | `command-palette.tsx`只有鼠标点击，无上下键选择/Enter确认 | VS Code/Raycast命令面板支持完整键盘导航(上下选择/Tab补全/Esc关闭) | P0 | 添加activeIndex状态，监听上下键切换焦点，Enter执行选中命令，Esc关闭面板 |
| 4 | 消息发送无动画反馈 | 点击发送后消息直接出现在列表中 | ChatGPT发送时有轻微弹跳动画；iMessage有发送气泡飞出效果 | P1 | 添加发送按钮点击时的scale缩小+恢复微动画；新消息用staggered fadeIn入场 |
| 5 | 拖拽面板无视觉反馈提示 | ResizablePanel拖拽时仅改变cursor，无视觉引导线 | VS Code面板拖拽时有蓝色高亮线指示 | P1 | 拖拽时divider变为2px蓝色高亮线，松开后恢复；添加双击divider重置默认宽度功能 |
| 6 | 滚动到底部无"新消息"提示 | MessageList仅自动滚动到底部，用户翻看历史时无法感知新消息到达 | Slack/Discord在用户浏览历史时显示"New messages"跳转按钮 | P1 | 添加滚动位置检测，非底部时显示悬浮"新消息"按钮，点击滚动到最新 |
| 7 | 追问建议无动画入场效果 | SuggestedQuestions直接渲染，无入场动画 | Perplexity追问建议有从下方滑入的staggered动画 | P2 | 每个追问按钮增加staggered fadeIn+slideUp动画(依次间隔50ms) |
| 8 | 无快捷键帮助面板 | 无地方查看所有可用快捷键 | TradingView有`?`键显示快捷键一览表 | P2 | 添加`?`或`Cmd+/`快捷键，弹出快捷键帮助面板 |
| 9 | 对话删除无确认/撤销 | ConversationSidebar删除对话直接执行，无确认弹窗 | ChatGPT删除对话有二次确认；Gmail有Undo按钮(5秒内可撤销) | P1 | 添加轻量级Toast确认(5秒内可撤销)或弹窗确认 |
| 10 | 添加持仓表单无验证反馈 | portfolio添加持仓时`if (newCode && newShares && newCost)`仅布尔检查，无错误提示 | 专业表单有实时校验+红色错误提示+输入框抖动 | P2 | 添加表单验证：股票代码格式校验(6位数字)、数量>0校验、成本>0校验，错误时高亮边框+提示文案 |
| 11 | 触摸设备拖拽不支持 | ResizablePanel只监听mousedown/mousemove/mouseup，无touch事件 | 响应式产品同时支持mouse和touch拖拽 | P1 | 添加touchstart/touchmove/touchend事件处理，或使用pointer events统一处理 |

---

### 维度4: AI交互体验 (11个)

| # | 差异点 | 当前状态 | 顶级标准 | 优先级 | 修复方案 |
|---|--------|---------|---------|--------|---------|
| 1 | 流式输出无逐字打字效果 | `appendStreamContent`直接拼接SSE返回的token块，ReactMarkdown一次性渲染完整文本 | ChatGPT/Claude有明显的逐字打字视觉效果 | P0 | SSE后端已按token返回；前端需确认每次append的粒度足够小(单字/单词)。若后端一次返回整段，需在前端用requestAnimationFrame逐字释放 |
| 2 | Agent思考过程缺乏过渡动画 | AgentProgressPanel直接渲染Agent状态网格，无入场/状态切换动画 | Perplexity搜索过程有步骤展开动画和进度环 | P0 | 每个AgentStatusBadge状态切换时添加颜色渐变动画；pending->running添加呼吸灯效果；running->done添加对勾弹出动画 |
| 3 | Artifact生成无入场动效 | ArtifactCard使用`animate-fade-in`(0.3s fadeIn)，效果过于简单 | Claude Artifacts有从右侧滑入+内容渐现的多层动画 | P1 | 改为从右侧slideIn+内容staggered fadeIn(标题先现->内容依次展开)，使用framer-motion的AnimatePresence |
| 4 | 工具调用无骨架屏过渡 | 工具调用中ToolCallCard仅显示"执行中..."文字+animate-pulse | Perplexity搜索过程展示骨架屏(Skeleton)预示结果形态 | P1 | 不同artifact_type对应不同骨架屏形态：K线图显示矩形骨架，数据卡显示行列骨架，雷达图显示圆形骨架 |
| 5 | 错误消息不可操作 | onError仅显示`"分析过程出错，请稍后重试"`文本消息 | ChatGPT错误消息有"Regenerate"重试按钮 | P0 | 错误消息增加"重试"按钮(重新发送最后一条用户消息)和"查看详情"折叠面板 |
| 6 | 无停止生成按钮 | 流式输出过程中无法中断 | ChatGPT/Claude有"Stop generating"按钮 | P0 | 在ChatInput组件isStreaming时显示"停止生成"按钮，点击时abort SSE连接(AbortController) |
| 7 | 流式Markdown光标过于简陋 | 用`span className="w-2 h-4 bg-primary animate-pulse"`模拟光标 | ChatGPT光标是精致的竖线闪烁效果，与文字同行 | P2 | 光标改为1px宽的竖线，使用`@keyframes blink`(opacity 0->1->0)，颜色跟随primary |
| 8 | 无消息编辑/重新生成功能 | 发送后的消息不可编辑或重新生成 | ChatGPT支持编辑历史消息重新生成 | P1 | 用户消息hover显示编辑图标，点击可修改后重新提交；AI消息显示"重新生成"按钮 |
| 9 | Agent进度面板无折叠功能 | AgentProgressPanel始终展开在消息流中 | 可折叠/展开的进度详情面板 | P2 | 进度面板默认显示精简一行(进度百分比+活跃Agent数)，点击展开完整网格和工具调用详情 |
| 10 | 无AI分析完成通知 | 长时间分析完成后无通知(用户可能已切换标签页) | 浏览器通知/Tab标题闪烁提醒分析完成 | P2 | 分析完成时发送浏览器Notification(需用户授权)或Tab标题加前缀闪烁"[完成]" |
| 11 | follow-up问题来源不透明 | SuggestedQuestions直接展示问题文本，用户不知为何推荐 | Perplexity的追问有分类(深入/对比/相关)和来源说明 | P2 | 为每个追问添加分类图标(深入分析/对比/相关话题)和简短理由 |

---

### 维度5: 图表专业度 (11个)

| # | 差异点 | 当前状态 | 顶级标准 | 优先级 | 修复方案 |
|---|--------|---------|---------|--------|---------|
| 1 | K线图无时间范围切换按钮 | CandlestickChart直接渲染所有数据，无1D/1W/1M/3M/1Y/ALL切换 | TradingView顶部有时间范围选择栏(1m/5m/15m/1h/1D/1W/1M) | P0 | 在K线图上方添加时间范围按钮组，点击后请求对应时间段数据重新渲染 |
| 2 | K线图无技术指标切换面板 | 仅硬编码MA5/MA20/MA60三条均线，无切换/添加其他指标功能 | TradingView可添加/移除100+指标(MACD/KDJ/BOLL/RSI子图等) | P0 | 添加指标选择下拉菜单，至少支持切换MA/MACD/KDJ/BOLL/RSI，MACD/KDJ渲染为独立子图区域 |
| 3 | K线图无绘图工具 | 无趋势线/水平线/斐波那契等绘图工具 | TradingView有完整绘图工具栏 | P2 | 利用lightweight-charts插件系统添加基础绘图工具(趋势线/水平线)，渲染在图表overlay层 |
| 4 | K线图十字线无价格/时间标签 | `crosshair: { mode: 0 }`启用十字线但无自定义tooltip显示OHLCV详情 | TradingView十字线附带价格标尺标签和时间标尺标签，顶部OHLCV信息实时更新 | P0 | 添加crosshairMove事件监听，在图表上方显示动态OHLCV信息条(O:xx H:xx L:xx C:xx V:xx) |
| 5 | 图表无loading骨架屏 | artifact-renderer.tsx中K线图loading用`div className="h-[400px] animate-pulse bg-muted rounded"` | TradingView加载时显示图表形状骨架(含假K线轮廓) | P1 | 替换为K线形状骨架屏SVG(矩形+影线排列的灰色占位) |
| 6 | 雷达图无交互功能 | ScoreRadarArtifact渲染静态雷达图，hover无详情显示 | 交互式雷达图hover显示具体分值和解读 | P1 | 添加Recharts Tooltip，hover维度显示具体分值+评级(如"趋势: 75分 - 中等偏强") |
| 7 | 资金流柱状图tooltip无格式化 | CapitalFlowArtifact的`<Tooltip />`使用默认样式 | 专业金融图表tooltip有格式化数字、颜色编码、多行信息 | P1 | 自定义Tooltip组件，显示日期/净流入金额(格式化)+颜色编码+与昨日对比 |
| 8 | 图表无右键菜单 | 无图表右键操作(如截图/导出数据/添加到自选) | TradingView右键菜单支持截图/导出/设置等 | P2 | 添加自定义右键菜单：截图保存/导出CSV/设置图表参数 |
| 9 | K线图成交量与K线间无联动高亮 | 成交量柱和K线仅颜色对应，hover时无联动 | TradingView hover某根K线时对应成交量柱同时高亮 | P1 | 利用lightweight-charts的crosshair联动机制同步高亮成交量柱 |
| 10 | 图表无水印/标识 | 无股票名称/代码水印覆盖在图表上 | TradingView图表左上角有股票代码+名称水印 | P2 | 添加图表水印层：左上角显示`股票代码 股票名称`半透明文字 |
| 11 | 图表resize体验不流畅 | ResizeObserver触发chart.applyOptions，但面板拖拽时可能频繁触发导致卡顿 | TradingView面板缩放流畅无抖动 | P1 | 添加ResizeObserver的throttle/debounce(16ms)优化，拖拽过程中降低图表渲染频率 |

---

### 维度6: 响应式设计 (10个)

| # | 差异点 | 当前状态 | 顶级标准 | 优先级 | 修复方案 |
|---|--------|---------|---------|--------|---------|
| 1 | 移动端对话侧边栏直接隐藏 | `@media (max-width: 1024px) { .conversation-sidebar { display: none; } }` | Robinhood移动端有可滑出的侧边栏；ChatGPT有汉堡菜单呼出 | P0 | 移动端将侧边栏改为可滑出的Sheet/Drawer组件，通过汉堡菜单或左滑手势打开 |
| 2 | 移动端Chat+Artifact面板体验差 | 移动端两面板各占50vh上下堆叠，chat-panel和artifact-panel各最高50vh | Robinhood移动端用Tab切换不同视图；ChatGPT移动端Artifact弹出全屏 | P0 | 移动端改为Tab切换模式(Chat/分析结果)或Artifact弹出为底部Sheet(可上滑全屏) |
| 3 | 投资组合页面移动端grid崩溃 | `grid grid-cols-3`在小屏幕不会自动降列 | Robinhood投资组合移动端为单列卡片堆叠 | P0 | 改为`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`响应式列数 |
| 4 | 移动端无底部Tab导航 | 移动端隐藏了侧边栏，导航仅靠顶部Navbar | Robinhood/同花顺移动端有底部Tab导航(首页/市场/交易/我的) | P1 | 移动端添加固定底部TabBar(对话/市场/组合/设置)，隐藏顶部Navbar部分功能 |
| 5 | 移动端市场概览ticker条不可滑动 | MarketOverview用`overflow-x-auto`但无滑动提示 | 同花顺顶部ticker条可左右滑动查看更多指数，有滚动渐隐提示 | P2 | 添加左右渐隐mask-image提示可滑动；或改为自动轮播ticker |
| 6 | 平板端无专属布局 | 平板(768px-1024px)仅隐藏侧边栏，其余与桌面端相同 | iPad版TradingView有优化的两栏布局(图表占大部分+侧面板) | P2 | 添加`@media (min-width: 768px) and (max-width: 1024px)`专属布局：Chat和Artifact改为可切换Tab |
| 7 | 移动端触摸手势缺失 | 无左右滑动切换面板、无下拉刷新 | 原生金融App支持左滑删除、右滑返回、下拉刷新 | P2 | 添加touch手势：聊天区下拉刷新历史消息，自选股左滑删除，面板左右滑切换 |
| 8 | 大屏优化不足 | 仅有`@media (min-width: 1920px) { .chat-panel { max-width: 500px; } }` | Bloomberg在4K屏幕上有多窗口/多Monitor布局支持 | P2 | 大屏增加多列Artifact展示(grid-cols-2)，利用额外空间展示更多信息面板 |
| 9 | 图表在移动端不可交互 | K线图和雷达图在触摸屏缺乏捏合缩放支持 | TradingView移动端支持双指缩放、单指拖动 | P1 | lightweight-charts原生支持触摸手势，确认`handleScroll`和`handleScale`配置已启用 |
| 10 | 移动端输入体验差 | chat-input在移动端键盘弹出时可能被遮挡 | ChatGPT移动端输入框随键盘上推，不被遮挡 | P1 | 添加`visualViewport` API监听，键盘弹出时调整布局；或使用`position: sticky bottom:0` |

---

### 维度7: 状态管理完整性 (10个)

| # | 差异点 | 当前状态 | 顶级标准 | 优先级 | 修复方案 |
|---|--------|---------|---------|--------|---------|
| 1 | API错误全部静默吞掉 | ConversationSidebar三处`catch { // 忽略 }`，MarketOverview也是`catch { setLoading(false) }` | 用户应知晓网络错误并可手动重试 | P0 | 所有API调用的catch块显示Toast/Snackbar错误提示，含"重试"按钮 |
| 2 | 无网络断开/重连提示 | 网络断开时无任何UI反馈 | Slack/Discord在网络断开时顶部显示"Connecting..."黄色横条 | P0 | 添加全局网络状态监听(navigator.onLine + 心跳检测)，离线时显示顶部Warning横条 |
| 3 | SSE无自动重连机制 | `use-chat-stream.ts`的streamPost若断连则错误被catch后结束 | ChatGPT流式断连后自动重试(指数退避) | P0 | 在apiClient.streamPost中添加自动重连逻辑：3次重试、指数退避(1s/2s/4s)、超时放弃并提示用户 |
| 4 | 聊天状态无持久化 | chat-store用zustand纯内存状态，刷新页面丢失所有消息 | ChatGPT刷新后对话仍在(服务端持久化+本地缓存) | P1 | 添加zustand persist中间件将messages/activeConversationId持久化到localStorage |
| 5 | Artifact面板新对话时清空但无过渡 | `clearArtifacts()`直接清空数组 | 旧artifact应有淡出动画，新artifact有淡入动画 | P2 | 使用AnimatePresence包裹artifact列表，离开时fadeOut，进入时fadeIn |
| 6 | 加载态覆盖不完整 | MarketOverview有loading态，但ConversationSidebar/Portfolio无loading骨架屏 | 所有数据获取组件都应有Skeleton加载态 | P1 | 为ConversationSidebar添加对话列表骨架屏；Portfolio添加数据加载骨架屏 |
| 7 | 空态引导不充分 | Watchlist空态仅"暂无自选股"文字；Portfolio空态类似 | 空态应有说明性插图+操作引导按钮 | P2 | 空态添加插图+引导文案+操作按钮(如"搜索并添加第一只自选股") |
| 8 | 无乐观更新策略 | 添加/删除操作等待API返回后再更新UI | 现代应用先更新UI(乐观更新)，失败时回滚 | P2 | 添加/删除自选股/对话时先乐观更新UI，API失败则回滚+Toast报错 |
| 9 | 多标签页状态不同步 | 两个标签页打开同一应用，状态独立不同步 | 专业应用使用BroadcastChannel或SharedWorker同步状态 | P2 | 使用zustand的BroadcastChannel中间件或StorageEvent实现跨Tab状态同步 |
| 10 | 设置页参数不可调 | settings页面"默认研究深度"显示固定值`3`，"语义记忆"显示固定"已启用"，不可交互修改 | 所有设置项应可交互修改并持久化 | P1 | 研究深度改为Slider(1-5)，语义记忆改为Switch开关，值存入settings-store并持久化 |

---

### 维度8: 无障碍/可用性 (10个)

| # | 差异点 | 当前状态 | 顶级标准 | 优先级 | 修复方案 |
|---|--------|---------|---------|--------|---------|
| 1 | 无ARIA标签 | 所有自定义组件(ArtifactCard/CommandPalette/ConversationSidebar等)无aria属性 | WCAG 2.1 AA标准要求关键交互元素有aria-label/aria-role | P1 | 添加关键ARIA：`role="dialog"`(CommandPalette), `aria-label`(所有按钮), `role="list"`(消息列表), `aria-live="polite"`(流式内容区) |
| 2 | 键盘导航不完整 | Tab键无法在Chat输入/侧边栏/Artifact面板间顺畅切换 | 所有交互元素可通过Tab键按逻辑顺序到达 | P1 | 添加tabIndex管理，确保Tab顺序：侧边栏->消息区->输入框->Artifact面板 |
| 3 | 焦点管理缺失 | 发送消息/切换对话后焦点不回到输入框 | 操作完成后焦点自动回到合理位置 | P1 | 发送消息后、选择追问后、切换对话后，自动focus到输入框textarea |
| 4 | 对比度问题 | `text-[10px] text-muted-foreground/50`(时间戳)对比度极低 | WCAG AA要求文字对比度>=4.5:1 | P1 | 检查所有text-muted-foreground/50的元素，确保对比度>=4.5:1，必要时调高亮度/增大字号 |
| 5 | 无屏幕阅读器支持 | 图表(K线/雷达)对屏幕阅读器不可见 | 图表应有替代文字描述 | P2 | 为每个图表组件添加`aria-label`描述(如"K线图显示最近30天走势，最高价XX，最低价XX") |
| 6 | 颜色作为唯一信息载体 | 涨跌仅用红/绿色区分，色盲用户无法区分 | 颜色+形状/文字双重编码 | P1 | 涨增加上箭头符号，跌增加下箭头符号，不仅依赖颜色(已部分实现但不全面) |
| 7 | 动画无减弱动效支持 | 所有动画无`prefers-reduced-motion`媒体查询适配 | 尊重用户系统级减弱动效偏好 | P2 | 添加`@media (prefers-reduced-motion: reduce)`全局取消/简化所有动画 |
| 8 | 移动端无长按操作 | 自选股/持仓无长按弹出操作菜单 | 移动端通过长按触发上下文菜单 | P2 | 添加长按事件(500ms)弹出操作菜单(删除/编辑/分析) |
| 9 | 无跳过导航链接 | 无"跳到主内容"链接 | 屏幕阅读器用户需要跳过导航快速到达主内容 | P2 | 在body顶部添加visually-hidden的"跳到主内容"链接，focus时显示 |
| 10 | 表单无关联label | portfolio和watchlist的input用独立`<label>`但未用htmlFor/id关联 | label应通过htmlFor与input的id关联 | P2 | 为每个Input添加unique id，label添加对应htmlFor |

---

### 维度9: 性能优化 (10个)

| # | 差异点 | 当前状态 | 顶级标准 | 优先级 | 修复方案 |
|---|--------|---------|---------|--------|---------|
| 1 | 图表组件已做懒加载(good) | artifact-renderer.tsx所有图表用`dynamic(() => import(...), { ssr: false })`，这是正确做法 | -- | -- | 保持当前做法，已符合标准 |
| 2 | Recharts未做Tree-shaking | 从recharts导入`BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell`等 | 应从`recharts/es6`精确导入减小bundle | P1 | 验证Next.js + recharts的tree-shaking是否生效，若bundle过大考虑改用`@visx`轻量方案 |
| 3 | 消息列表未做虚拟滚动 | MessageList渲染所有messages，对话长时性能下降 | Slack/Discord使用虚拟滚动(react-window/react-virtualized) | P1 | 消息超过50条时启用react-window虚拟滚动，仅渲染可视区域消息 |
| 4 | SSE无AbortController | useChatStream创建的SSE流无法被用户取消 | 应使用AbortController支持取消 | P0 | 在streamPost调用时传入AbortController.signal，组件卸载或用户点击停止时abort |
| 5 | Markdown渲染无memo优化 | StreamMarkdown每次content变化重新完整解析Markdown | 历史消息的Markdown应缓存解析结果 | P1 | 非流式消息使用React.memo + useMemo缓存ReactMarkdown输出 |
| 6 | 图表销毁/重建过于频繁 | CandlestickChart useEffect依赖[data, theme, stockColorScheme]，主题切换时整个图表重建 | 主题切换应只更新样式，不重建图表 | P1 | 分离图表创建和样式更新：创建仅在data变化时执行，theme变化时仅applyOptions更新样式 |
| 7 | 无Service Worker缓存 | 无离线缓存/静态资源缓存策略 | 金融PWA应缓存Shell和常用数据 | P2 | 添加next-pwa配置，缓存App Shell和静态资源 |
| 8 | 无图片优化 | 未使用Next.js Image组件(当前无图片引用但未来可能有) | 应使用Next.js Image自动优化 | P2 | 建立规范：所有图片使用next/image组件 |
| 9 | zustand store无选择器优化 | 组件直接`useChatStore()`获取整个store，任何状态变化触发所有消费者重渲染 | 应使用选择器仅订阅需要的状态切片 | P1 | 改为`useChatStore(s => s.messages)`等选择器模式，减少不必要的重渲染 |
| 10 | 无Web Worker用于重计算 | 所有计算在主线程，包括portfolio的盈亏计算和数据格式化 | 重计算应offload到Web Worker避免阻塞UI | P2 | 当前计算量小可暂不处理，但大数据量(如多股票回测)应使用Web Worker |

---

### 维度10: 缺失功能 (15个)

| # | 差异点 | 当前状态 | 顶级标准 | 优先级 | 修复方案 |
|---|--------|---------|---------|--------|---------|
| 1 | 无实时行情推送 | 市场数据仅初始化加载一次 | Bloomberg/TradingView有WebSocket实时推送价格 | P0 | 建立WebSocket连接，订阅自选股实时行情，推送到market-overview和portfolio |
| 2 | 无股票搜索功能 | 用户必须手动输入6位股票代码 | 同花顺/TradingView有模糊搜索(输入名称/代码/拼音首字母) | P0 | 添加股票搜索组件：支持代码/名称/拼音搜索，下拉显示匹配结果+行业标签 |
| 3 | 无多股票对比页面 | 仅支持单股票分析 | TradingView支持多图表叠加/并排对比 | P1 | 添加/compare路由页面，支持选择2-4只股票并排展示K线和关键指标对比 |
| 4 | 无行业板块页面 | 无行业/板块分析入口 | 同花顺有行业板块热力图/涨跌排行 | P1 | 添加/sectors路由页面，展示行业板块热力图、涨幅排行、资金流向 |
| 5 | 无历史分析报告归档 | 分析结果仅在当前对话中，无法回溯 | FinChat有历史报告库/书签收藏 | P1 | 添加报告归档功能：每次完整分析生成可保存的报告，支持PDF导出 |
| 6 | 无价格预警/提醒 | 无设置价格触发提醒功能 | 同花顺/TradingView支持价格预警 | P2 | 添加价格预警设置面板(目标价/百分比变化)，通过浏览器通知提醒 |
| 7 | 无数据导出功能 | ArtifactCard的导出仅复制innerText到剪贴板 | 应支持CSV/Excel/PNG导出 | P1 | K线数据导出CSV，图表导出PNG(html2canvas)，分析报告导出PDF |
| 8 | 无国际化支持 | 所有文本硬编码中文 | Bloomberg支持多语言切换 | P2 | 建立i18n框架(next-intl)，抽取所有文本为翻译键，支持中/英切换 |
| 9 | 无用户认证系统 | 无登录/注册/权限管理 | 所有金融产品都有用户认证 | P1 | 集成NextAuth或clerk进行用户认证，保护API端点 |
| 10 | 后端agent_pipeline类型未实现专属渲染器 | artifact-renderer.tsx的switch中无agent_pipeline case，fallback到GenericDataView(JSON显示) | 应有可视化的Agent流水线图 | P1 | 实现AgentPipelineArtifact组件，用流程图形式展示各Agent的执行顺序和结果 |
| 11 | 无分析深度自定义 | settings显示"默认研究深度: 3"但不可调整 | 用户应能选择快速分析(1-2)或深度分析(4-5) | P1 | 在ChatInput旁或Settings中添加深度选择Slider(1-5)，传入sendMessage的research_depth参数 |
| 12 | 无图表主题同步 | K线图仅在data/theme依赖变化时重建 | 图表应实时跟随主题切换无缝变化 | P1 | 如维度9-6所述，theme变化时仅更新图表样式不重建 |
| 13 | 无分享功能 | 无法将分析结果分享给他人 | FinChat/Perplexity支持生成分享链接 | P2 | 添加分享按钮，生成可访问的分享链接(含分析快照) |
| 14 | 无键盘快捷键文档 | WelcomeScreen底部仅提示Enter/Shift+Enter/`/`三个快捷键 | TradingView有完整快捷键列表(Alt+T/F/L等) | P2 | 建立完整快捷键系统并在`?`菜单中展示 |
| 15 | 无暗色/亮色模式自动跟随系统 | theme-store手动切换，无`prefers-color-scheme`自动检测 | 现代应用默认跟随系统偏好，支持手动覆盖 | P1 | 添加"自动"主题选项，使用`matchMedia('(prefers-color-scheme: dark)')`检测系统偏好 |

---

## 优先级统计

| 优先级 | 数量 | 说明 |
|--------|------|------|
| P0 | 22 | 必须立即修复，影响核心用户体验 |
| P1 | 46 | 重要改进，1-2个迭代内完成 |
| P2 | 44 | 锦上添花，按资源排期 |

## P0差异点汇总（22个关键缺陷）

1. **金融数字字体缺失** — 全局缺乏tabular-nums特性
2. **市场概览数据全部硬编码为0** — 市场指数ticker无真实数据
3. **数字缺乏千分位格式化** — 无统一formatNumber工具
4. **涨跌颜色使用不一致** — portfolio硬编码green-500/red-500
5. **百分比格式不统一** — 正负号+小数位不一
6. **输入框无真正自动增高** — textarea高度固定
7. **无Cmd+K全局搜索** — 缺乏全局命令入口
8. **命令面板不支持键盘导航** — 仅鼠标可操作
9. **流式输出无逐字打字效果** — 可能一次出现大段文字
10. **Agent思考过程缺乏过渡动画** — 状态切换无动画
11. **错误消息不可操作** — 无重试按钮
12. **无停止生成按钮** — 流式输出不可中断
13. **K线图无时间范围切换** — 无1D/1W/1M切换
14. **K线图无技术指标切换** — 仅固定MA三线
15. **K线十字线无OHLCV信息条** — 无悬停数据详情
16. **移动端侧边栏直接隐藏** — 无替代导航方案
17. **移动端Chat+Artifact体验差** — 50vh堆叠不可用
18. **投资组合移动端grid崩溃** — 3列不响应式
19. **API错误全部静默吞掉** — 用户不知道请求失败
20. **无网络断开/重连提示** — 离线无感知
21. **SSE无自动重连和AbortController** — 断连后无法恢复/取消
22. **无实时行情推送和股票搜索** — 两个核心金融功能缺失

---

## 建议修复路线图

### 第一阶段（1-2周）: 核心可用性
- 修复所有P0项（22个）
- 重点：数据格式化统一、搜索功能、移动端适配、错误处理、停止生成

### 第二阶段（3-4周）: 专业度提升
- 修复P1项（46个）
- 重点：图表交互增强、状态持久化、ARIA无障碍、性能优化

### 第三阶段（5-8周）: 竞争力提升
- 修复P2项（44个）
- 重点：高级功能（对比页/行业板块/分享/导出）、动画精细化、PWA支持

---

*报告由评审Agent生成，隶属香草少校团队。*
