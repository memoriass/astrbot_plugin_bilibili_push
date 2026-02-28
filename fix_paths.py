import os
from pathlib import Path

plugin_dir = r"c:\git\AstrBot\data\plugins\astrbot_plugin_bilibili_push"

# Fix main.py
main_file = os.path.join(plugin_dir, "main.py")
with open(main_file, "r", encoding="utf-8") as f:
    main_content = f.read()

main_content = main_content.replace(
    'self.plugin_dir = Path(__file__).parent',
    '''self.plugin_dir = Path(__file__).parent
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path
        self.data_dir = Path(get_astrbot_data_path()) / "plugin_data" / "astrbot_plugin_bilibili_push"
        self.data_dir.mkdir(parents=True, exist_ok=True)'''
)

main_content = main_content.replace(
    'self.temp_dir = self.plugin_dir / "temp"',
    'self.temp_dir = self.data_dir / "temp"'
)

main_content = main_content.replace(
    'self.temp_dir.mkdir(exist_ok=True)',
    '''self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.bg_dir = self.data_dir / "backgrounds"
        self.bg_dir.mkdir(parents=True, exist_ok=True)'''
)

main_content = main_content.replace(
    'self.db = DatabaseManager(self.plugin_dir / "data" / "bilibili_push.db")',
    'self.db = DatabaseManager(self.data_dir / "data.db")' # Restoring the old DB path
)

main_content = main_content.replace(
    'self.help_handler = HelpHandler(context)',
    'self.help_handler = HelpHandler(context, self.bg_dir)'
)
main_content = main_content.replace(
    'self.sub_handler = SubscriptionHandler(context, self.db)',
    'self.sub_handler = SubscriptionHandler(context, self.db, self.bg_dir)'
)
main_content = main_content.replace(
    'self.search_handler = SearchHandler(context)',
    'self.search_handler = SearchHandler(context, self.bg_dir)'
)

with open(main_file, "w", encoding="utf-8") as f:
    f.write(main_content)
    
# Fix HelpHandler
help_file = os.path.join(plugin_dir, "handlers", "help_handler.py")
with open(help_file, "r", encoding="utf-8") as f:
    help_content = f.read()

help_content = help_content.replace(
    'def __init__(self, context: Context):',
    'def __init__(self, context: Context, bg_dir: Path):'
)
help_content = help_content.replace(
    'self.bg_folder = get_assets_path() / "backgrounds" / "help"',
    'self.bg_folder = bg_dir'
)

with open(help_file, "w", encoding="utf-8") as f:
    f.write(help_content)

# Fix SubscriptionHandler
sub_file = os.path.join(plugin_dir, "handlers", "subscription_handler.py")
with open(sub_file, "r", encoding="utf-8") as f:
    sub_content = f.read()

sub_content = sub_content.replace(
    'def __init__(self, context: Context, db):',
    'def __init__(self, context: Context, db, bg_dir: Path):'
)
sub_content = sub_content.replace(
    'self.bg_folder = get_assets_path() / "backgrounds"',
    'self.bg_folder = bg_dir'
)
# Make sure it doesn't append /help to bg_folder
sub_content = sub_content.replace(
    'get_random_background(self.bg_folder / "help")',
    'get_random_background(self.bg_folder)'
)
with open(sub_file, "w", encoding="utf-8") as f:
    f.write(sub_content)

# Fix SearchHandler
search_file = os.path.join(plugin_dir, "handlers", "search_handler.py")
with open(search_file, "r", encoding="utf-8") as f:
    search_content = f.read()

search_content = search_content.replace(
    'from ..utils.resource import get_template_path',
    'from ..utils.resource import get_template_path, get_random_background'
)
search_content = search_content.replace(
    'def __init__(self, context: Context):',
    'def __init__(self, context: Context, bg_dir: Path):\n        self.bg_dir = bg_dir'
)
search_content = search_content.replace(
    '"bg_image_uri": ""',
    '"bg_image_uri": get_random_background(self.bg_dir)["uri"]'
)

with open(search_file, "w", encoding="utf-8") as f:
    f.write(search_content)

print("Modification scripts completed successfully!")
