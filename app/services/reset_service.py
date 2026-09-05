"""系统重置：清空测试数据并重建初始管理员与默认语言。"""
from app import storage
from app.bootstrap import default_languages
from app.services import ai_service, submission_service, user_service


async def reset_all():
    for store in (
        storage.db.problems,
        storage.db.users,
        storage.db.submissions,
        storage.db.languages,
        storage.db.ai_tasks,
    ):
        for key in list(store.data.keys()):
            await store.delete(key)

    await storage.db.access_log.clear()
    await storage.db.ai_config.clear()
    ai_service.clear_runtime()
    submission_service.clear_rate_limit()

    await user_service.create_user("admin", "admintestpassword", role="admin")
    for name, lang in default_languages().items():
        await storage.db.languages.put(name, lang)
