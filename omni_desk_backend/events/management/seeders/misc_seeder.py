"""辅助数据 Seeder：沟通帖子、新闻、备忘录、配置"""

import random
from datetime import date, datetime, timedelta, timezone as dt_tz
from communication.models import Post, Comment as CommComment
from news.models import NewsType, NewsArticle
from memos.models import Memo
from config.models import Config
from events.management.seeders.base import BaseSeeder


class MiscSeeder(BaseSeeder):
    name = "辅助数据"
    order = 60
    models = [Post, CommComment, NewsType, NewsArticle, Memo, Config]

    def seed(self):
        user = self.context.get("user")

        # 沟通帖子
        post_titles = [
            "关于下周设备校准的安排",
            "新项目启动通知",
            "安全培训报名开始",
            "实验室使用规范更新",
        ]
        posts = []
        for title in post_titles:
            obj, _ = self.safe_get_or_create(
                Post,
                title=title,
                defaults={"content": f"这是一条关于{title}的内部通知，请大家及时关注。", "author": user},
            )
            posts.append(obj)

        # 评论
        if user and posts:
            for post in posts[:2]:
                CommComment.objects.get_or_create(
                    post=post,
                    author=user,
                    defaults={"content": "收到，会按时参加。"},
                )

        # 新闻
        news_types = ["公司动态", "行业新闻", "技术资讯"]
        type_objs = []
        for name in news_types:
            obj, _ = NewsType.objects.get_or_create(name=name)
            type_objs.append(obj)

        news_items = [
            ("我国成功发射新一代导航卫星", "https://example.com/news/1", type_objs[0]),
            ("国际传感器技术发展趋势报告发布", "https://example.com/news/2", type_objs[1]),
            ("新型MEMS传感器突破技术瓶颈", "https://example.com/news/3", type_objs[1]),
        ]
        for title, link, ntype in news_items:
            self.safe_get_or_create(
                NewsArticle,
                title=title,
                defaults={
                    "link": link,
                    "publication_date": date.today() - timedelta(days=random.randint(1, 30)),
                    "personnel": user,
                    "news_type": ntype,
                },
            )

        # 备忘录
        if user:
            memos_data = [
                ("准备月度汇报材料", "需要在月底前完成月度工作汇报PPT", 2),
                ("联系设备供应商", "确认新设备的交付时间", 1),
                ("安排新员工入职培训", "下周有新员工入职，需要提前准备", 3),
            ]
            for title, content, days in memos_data:
                reminder = datetime.combine(
                    date.today() + timedelta(days=days),
                    datetime.min.time().replace(hour=9),
                    tzinfo=dt_tz.utc,
                )
                Memo.objects.get_or_create(
                    title=title,
                    user=user,
                    defaults={"content": content, "reminder_time": reminder, "is_completed": False},
                )

        # 系统配置
        Config.objects.get_or_create(
            key="site_name",
            defaults={"value": "OmniDesk 综合管理系统", "description": "站点名称"},
        )
        Config.objects.get_or_create(
            key="site_version",
            defaults={"value": "1.0.0", "description": "系统版本"},
        )

        return [
            ("沟通帖子", len(post_titles)),
            ("新闻", len(news_items)),
            ("备忘录", 3),
            ("系统配置", 2),
        ]
