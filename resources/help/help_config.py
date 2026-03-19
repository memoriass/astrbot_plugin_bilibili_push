"""Bilibili 插件帮助配置 - Miao-Plugin 风格"""

# 帮助配置
HELP_CONFIG = {
    # 帮助标题
    "title": "Bilibili 推送帮助",
    
    # 帮助副标题
    "subTitle": "Bilibili Dynamic & Live Push Plugin",
    
    # 帮助表格列数，可选：2-5，默认3
    "colCount": 3,
    
    # 单列宽度，默认265
    "colWidth": 265,
}

# 帮助菜单内容（从 main.py 中提取的真实命令）
HELP_LIST = [
    {
        "group": "帮助信息",
        "list": [
            {
                "icon": 79,
                "title": "b站帮助",
                "desc": "显示帮助菜单图卡"
            }
        ]
    },
    {
        "group": "动态追踪",
        "list": [
            {
                "icon": 61,
                "title": "添加b站订阅 <UID>",
                "desc": "添加动态订阅"
            },
            {
                "icon": 35,
                "title": "取消b站订阅 <UID>",
                "desc": "取消动态订阅"
            },
            {
                "icon": 67,
                "title": "b站订阅列表",
                "desc": "列出本会话的所有订阅"
            }
        ]
    },
    {
        "group": "直播提醒",
        "list": [
            {
                "icon": 64,
                "title": "添加b站直播 <UID>",
                "desc": "添加直播订阅"
            },
            {
                "icon": 35,
                "title": "取消b站直播 <UID>",
                "desc": "取消直播提醒"
            }
        ]
    },
    {
        "group": "账号管理",
        "list": [
            {
                "icon": 22,
                "title": "b站登录",
                "desc": "扫码登录 B站 账号"
            },
            {
                "icon": 85,
                "title": "b站登录状态",
                "desc": "查看当前已登录的账号池状态"
            }
        ]
    },
    {
        "group": "搜索工具",
        "list": [
            {
                "icon": 83,
                "title": "b站搜索 <关键词>",
                "desc": "在 B站 快速搜索 UP 主并获取 UID"
            }
        ]
    }
]

