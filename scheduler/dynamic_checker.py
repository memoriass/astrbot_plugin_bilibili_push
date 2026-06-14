from ..database.db_manager import Subscription
from ..utils.logger import logger
from .subscription_group import group_subscriptions


class DynamicSubscriptionChecker:
    def __init__(self, platform, dispatcher, star=None):
        self.platform = platform
        self.dispatcher = dispatcher
        self.star = star
        self.seen_posts: dict[str, set[str]] = {}

    async def check(self, subs: list[Subscription]):
        for sub_unit in group_subscriptions(subs):
            uid = sub_unit.sub_target
            try:
                posts = await self.platform.fetch_new_post(sub_unit)
                await self._load_seen_posts(uid)

                if uid not in self.seen_posts:
                    await self._init_seen_posts(uid, posts)
                    continue

                new_posts = self._collect_new_posts(uid, posts)
                self._trim_seen_posts(uid, posts)

                if new_posts and self.star:
                    await self.star.put_kv_data(
                        f"seen_posts_{uid}", list(self.seen_posts[uid])
                    )
                if new_posts:
                    await self.dispatcher.dispatch(
                        self.platform.platform_name,
                        new_posts,
                        sub_unit.user_sub_infos,
                    )
            except Exception as exc:
                logger.error(f"动态检查失败 {uid}: {exc}")

    async def _load_seen_posts(self, uid: str):
        if uid in self.seen_posts or not self.star:
            return
        cached = await self.star.get_kv_data(f"seen_posts_{uid}", [])
        if cached:
            self.seen_posts[uid] = set(cached)

    async def _init_seen_posts(self, uid: str, posts):
        self.seen_posts[uid] = {post.id for post in posts}
        if self.star:
            await self.star.put_kv_data(f"seen_posts_{uid}", list(self.seen_posts[uid]))

    def _collect_new_posts(self, uid: str, posts):
        new_posts = []
        for post in posts:
            if post.id not in self.seen_posts[uid]:
                new_posts.append(post)
                self.seen_posts[uid].add(post.id)
        return new_posts

    def _trim_seen_posts(self, uid: str, posts):
        if len(self.seen_posts[uid]) <= 100:
            return
        self.seen_posts[uid] = {
            post.id for post in sorted(posts, key=lambda x: x.timestamp, reverse=True)[:100]
        }
