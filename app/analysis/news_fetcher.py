# news_fetcher.py
# -*- coding: utf-8 -*-
"""
Input: AKShare stock_info_global_cls 财联社电报原始数据 (含标题/内容/发布日期/发布时间)
Output: JSON文件(每日1个)，每条新闻含统一字段:
  - title (若上游空则从content首40字派生)
  - content
  - date/time/datetime/fetch_time (向后兼容旧字段)
  - published_at (R1 Q3契约: ISO8601 +08:00 统一时间, 前端优先使用)
  - source (R1 Q3契约: "财联社"|"新浪财经"|... 前端展示来源)
  - hash (内容指纹去重)
Pos: 后端新闻管道唯一入口 (app/analysis/news_fetcher.py), 被 web_server.py /api/latest_news 调用
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""

import os
import json
import logging
import time
import hashlib
from datetime import datetime, timedelta, date, timezone
import akshare as ak

_ASIA_SHANGHAI = timezone(timedelta(hours=8))
now_cn = lambda: datetime.now(_ASIA_SHANGHAI)
import pandas as pd

# 设置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('news_fetcher')

# 自定义JSON编码器，处理日期类型
class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if pd.isna(obj):  # 处理pandas中的NaN
            return None
        return super(DateEncoder, self).default(obj)

class NewsFetcher:
    def __init__(self, save_dir="data/news"):
        """初始化新闻获取器"""
        self.save_dir = save_dir
        # 确保保存目录存在
        os.makedirs(self.save_dir, exist_ok=True)
        self.last_fetch_time = None

        # 哈希集合用于快速判断新闻是否已存在
        self.news_hashes = set()
        # 加载已有的新闻哈希
        self._load_existing_hashes()

    def _load_existing_hashes(self):
        """加载已有文件中的新闻哈希值"""
        try:
            # 获取最近7天的文件来加载哈希值
            today = now_cn()
            for i in range(7):  # 检查最近7天的数据
                date = today - timedelta(days=i)
                filename = self.get_news_filename(date)

                if os.path.exists(filename):
                    with open(filename, 'r', encoding='utf-8') as f:
                        try:
                            news_data = json.load(f)
                            for item in news_data:
                                # 如果有哈希字段就直接使用，否则计算新的哈希
                                if 'hash' in item:
                                    self.news_hashes.add(item['hash'])
                                else:
                                    content_hash = self._calculate_hash(item['content'])
                                    self.news_hashes.add(content_hash)
                        except json.JSONDecodeError:
                            logger.warning(f"文件 {filename} 格式错误，跳过加载哈希值")

            logger.info(f"已加载 {len(self.news_hashes)} 条新闻哈希值")

            # 限制哈希集合大小，防止内存无限增长
            MAX_HASHES = 50000
            if len(self.news_hashes) > MAX_HASHES:
                # 保留最近的哈希（集合无序，但控制上限）
                self.news_hashes = set(list(self.news_hashes)[-MAX_HASHES:])
                logger.info(f"哈希集合超过上限，已截断至 {MAX_HASHES} 条")

        except Exception as e:
            logger.error(f"加载新闻哈希时出错: {str(e)}")
            # 不清空已加载的哈希，保留部分去重能力

    @staticmethod
    def _derive_title(content: str, max_len: int = 40) -> str:
        """R1 Q3契约: 财联社电报多数条目title为空, 从content首段派生简短标题。
        优先以中英文句号/问号/感叹号断句, 否则按max_len硬截断。"""
        if not content:
            return ""
        text = str(content).strip()
        if not text:
            return ""
        # 尝试以首个句末标点断句
        for punct in ("。", "！", "？", ".", "!", "?"):
            idx = text.find(punct)
            if 0 < idx <= max_len:
                return text[:idx].strip()
        if len(text) <= max_len:
            return text
        return text[:max_len].rstrip() + "…"

    @staticmethod
    def _compose_published_at(pub_date: str, pub_time: str) -> str:
        """R1 Q3契约: 将后端异构 date/time 字段组装为 ISO8601 +08:00。
        若解析失败则返回空字符串(前端应兜底到旧 datetime/publish_time 字段)。"""
        try:
            pd_str = (pub_date or "").strip()
            pt_str = (pub_time or "").strip()
            if not pd_str and not pt_str:
                return ""
            # 纯时间 HH:MM:SS 情况: 补今日日期
            if not pd_str and pt_str:
                pd_str = now_cn().strftime("%Y-%m-%d")
            # 纯日期: 补 00:00:00
            if pd_str and not pt_str:
                pt_str = "00:00:00"
            # 尝试宽松解析
            combined = f"{pd_str} {pt_str}"
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                        "%Y/%m/%d %H:%M:%S", "%Y%m%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(combined, fmt)
                    return dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")
                except ValueError:
                    continue
            return ""
        except Exception:
            return ""

    def _calculate_hash(self, content):
        """计算内容哈希，带文本规范化"""
        if not content:
            return None
        # 规范化：去除多余空白、统一格式
        normalized = ' '.join(str(content).split()).strip()
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()

    def get_news_filename(self, date=None):
        """获取指定日期的新闻文件名"""
        if date is None:
            date = now_cn().strftime('%Y%m%d')
        else:
            date = date.strftime('%Y%m%d')
        return os.path.join(self.save_dir, f"news_{date}.json")

    def fetch_and_save(self):
        """获取新闻并保存到JSON文件，避免重复内容"""
        try:
            # 获取当前时间
            now = now_cn()

            # 调用AKShare API获取财联社电报数据
            logger.info("开始获取财联社电报数据")
            stock_info_global_cls_df = ak.stock_info_global_cls(symbol="全部")

            if stock_info_global_cls_df.empty:
                logger.warning("获取的财联社电报数据为空")
                return False

            # 打印DataFrame的信息和类型，帮助调试
            logger.info(f"获取的数据形状: {stock_info_global_cls_df.shape}")
            logger.info(f"数据列: {stock_info_global_cls_df.columns.tolist()}")
            logger.info(f"数据类型: \n{stock_info_global_cls_df.dtypes}")

            # 计数器
            total_count = 0
            new_count = 0

            # 转换为列表字典格式并添加哈希值
            news_list = []
            for _, row in stock_info_global_cls_df.iterrows():
                total_count += 1

                # 安全获取内容和标题，确保为字符串
                content = str(row.get("内容", ""))
                title = str(row.get("标题", ""))

                # 组合标题和内容进行去重
                combined = f"{title}||{content}"
                content_hash = self._calculate_hash(combined)

                # 检查是否已存在相同内容的新闻
                if content_hash in self.news_hashes:
                    continue  # 跳过已存在的新闻

                # 添加新的哈希值到集合
                self.news_hashes.add(content_hash)
                new_count += 1

                # 安全获取日期和时间，确保为字符串格式
                pub_date = row.get("发布日期", "")
                if isinstance(pub_date, (datetime, date)):
                    pub_date = pub_date.isoformat()
                else:
                    pub_date = str(pub_date)

                pub_time = row.get("发布时间", "")
                if isinstance(pub_time, (datetime, date)):
                    pub_time = pub_time.isoformat()
                else:
                    pub_time = str(pub_time)

                # R1 Q3契约: title空则从content派生
                effective_title = title.strip() if title and title.strip() else self._derive_title(content)

                # R1 Q3契约: 统一ISO8601时间
                published_at = self._compose_published_at(pub_date, pub_time)

                # 创建新闻项并添加哈希值
                news_item = {
                    "title": effective_title,
                    "content": content,
                    "date": pub_date,
                    "time": pub_time,
                    "datetime": f"{pub_date} {pub_time}",
                    "fetch_time": now.strftime('%Y-%m-%d %H:%M:%S'),
                    # R1 Q3契约新增字段 (前端优先消费)
                    "published_at": published_at,
                    "source": "财联社",
                    "hash": content_hash  # 保存哈希值以便后续使用
                }
                news_list.append(news_item)

            # 如果没有新的新闻，直接返回
            if not news_list:
                logger.info(f"没有新的新闻数据需要保存 (共检查 {total_count} 条)")
                return True

            # 获取文件名
            filename = self.get_news_filename()

            # 如果文件已存在，则合并新旧数据
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    try:
                        existing_data = json.load(f)
                        # 合并数据，已经确保news_list中的内容都是新的
                        merged_news = existing_data + news_list
                        # 按时间排序
                        merged_news.sort(key=lambda x: x['datetime'], reverse=True)
                    except json.JSONDecodeError:
                        logger.warning(f"文件 {filename} 格式错误，使用新数据替换")
                        merged_news = sorted(news_list, key=lambda x: x['datetime'], reverse=True)
            else:
                # 如果文件不存在，直接使用新数据
                merged_news = sorted(news_list, key=lambda x: x['datetime'], reverse=True)

            # 保存合并后的数据，使用自定义编码器处理日期
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(merged_news, f, ensure_ascii=False, indent=2, cls=DateEncoder)

            logger.info(f"成功保存 {new_count} 条新闻数据 (共检查 {total_count} 条，过滤重复 {total_count - new_count} 条)")
            self.last_fetch_time = now
            return True

        except Exception as e:
            logger.error(f"获取或保存新闻数据时出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())  # 打印完整的堆栈跟踪，便于调试
            return False

    def get_latest_news(self, days=1, limit=50):
        """获取最近几天的新闻数据，并去除重复项"""
        news_data = []
        today = now_cn()
        # 记录已处理的日期，便于日志
        processed_dates = []

        # 获取指定天数内的所有新闻
        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime('%Y%m%d')
            filename = self.get_news_filename(date)

            if os.path.exists(filename):
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        news_data.extend(data)
                        processed_dates.append(date_str)
                        logger.info(f"已加载 {date_str} 新闻数据 {len(data)} 条")
                except Exception as e:
                    logger.error(f"读取文件 {filename} 时出错: {str(e)}")
            else:
                logger.warning(f"日期 {date_str} 的新闻文件不存在: {filename}")

        # 排序前记录总数
        total_before_sort = len(news_data)

        # 去除重复项
        # 使用内容哈希或已有的哈希字段作为唯一标识
        unique_news = {}
        duplicate_count = 0

        for item in news_data:
            # 优先使用已有的哈希值，如果没有则组合标题+内容计算哈希
            item_hash = item.get('hash')
            if not item_hash and 'content' in item:
                combined = f"{item.get('title', '')}||{item['content']}"
                item_hash = self._calculate_hash(combined)

            # 如果是新的哈希值，则添加到结果中
            if item_hash and item_hash not in unique_news:
                unique_news[item_hash] = item
            else:
                duplicate_count += 1

        # 转换回列表并按时间排序
        deduplicated_news = list(unique_news.values())
        deduplicated_news.sort(key=lambda x: x.get('datetime', ''), reverse=True)

        # 限制返回条数
        result = deduplicated_news[:limit]

        # R1 Q3契约: 对历史文件中缺失 title/published_at/source 的条目做"输出时回填"
        # (不重写磁盘文件, 保持向后兼容; 仅保证 API 出参统一)
        for it in result:
            try:
                # title 空 → 从 content 派生
                t = it.get("title")
                if not (t and str(t).strip()):
                    it["title"] = self._derive_title(it.get("content", ""))
                # published_at 缺失 → 从 date+time 组装
                if not it.get("published_at"):
                    pa = self._compose_published_at(it.get("date", ""), it.get("time", ""))
                    if pa:
                        it["published_at"] = pa
                # source 缺失 → 默认财联社 (当前唯一数据源)
                if not it.get("source"):
                    it["source"] = "财联社"
            except Exception:
                continue

        logger.info(f"获取最近 {days} 天新闻(处理日期:{','.join(processed_dates)}), "
                    f"共 {total_before_sort} 条, 去重后 {len(deduplicated_news)} 条, "
                    f"移除重复 {duplicate_count} 条, 返回最新 {len(result)} 条")

        return result

# 单例模式的新闻获取器
news_fetcher = NewsFetcher()

def fetch_news_task():
    """执行新闻获取任务"""
    logger.info("开始执行新闻获取任务")
    news_fetcher.fetch_and_save()
    logger.info("新闻获取任务完成")


def _background_scheduler_enabled():
    """测试/离线环境不启动真实新闻后台调度；默认开发启动保持开启。"""
    return os.getenv("DISABLE_NETWORK", "0") != "1"


def start_news_scheduler():
    """启动新闻获取定时任务"""
    if not _background_scheduler_enabled():
        logger.info("DISABLE_NETWORK=1，跳过新闻获取定时任务启动")
        return None

    import threading
    import time

    def _run_scheduler():
        while True:
            try:
                fetch_news_task()
                # 等待3分钟
                time.sleep(180)
            except Exception as e:
                logger.error(f"定时任务执行出错: {str(e)}")
                time.sleep(60)  # 出错后等待1分钟再试

    # 创建并启动定时任务线程
    scheduler_thread = threading.Thread(target=_run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    logger.info("新闻获取定时任务已启动")
    return scheduler_thread

# 初始获取一次数据
if __name__ == "__main__":
    fetch_news_task()
