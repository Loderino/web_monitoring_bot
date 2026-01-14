from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.tg_handler import TGHandler
from constants import TG_BOT_TOKEN
from scheduler import Scheduler

class TGBot:
    """
    Class for Telegram bot.

    The class provides ability to setup Telegram bot with custom handlers for different types of updates.
    """

    def __init__(self) -> None:
        self.actions_handler: TGHandler = None
        self.scheduler = None
        self.bot = (
            ApplicationBuilder()
            .token(TG_BOT_TOKEN)
            .concurrent_updates(True)
            .http_version("1.1")
            .get_updates_http_version("1.1")
            .post_init(self.initialize_scheduler)
            .build()
        )

    async def initialize_scheduler(self, application: ApplicationBuilder) -> None:
        self.scheduler = Scheduler()
        self.actions_handler = TGHandler(self.scheduler._manager._status_manager, application.bot)
        self.add_handlers()

    def add_handlers(self) -> None:
        """
        Adding handlers to the bot.
        """
        self.bot.add_handler(CommandHandler("start", self.actions_handler.start))
        self.bot.add_handler(CommandHandler("help", self.actions_handler.help))
        self.bot.add_handler(CommandHandler("monitors", self.actions_handler.monitors))
        self.bot.add_handler(CallbackQueryHandler(self.actions_handler.handle_buttons))
        self.bot.add_handler(
            MessageHandler(
                ~filters.COMMAND
                & filters.Regex(self.actions_handler.strings.button.panel.my_monitors),
                self.actions_handler.monitors,
            )
        )
        self.bot.add_handler(
            MessageHandler(
                ~filters.COMMAND
                & filters.Regex(self.actions_handler.strings.button.panel.add_monitor),
                self.actions_handler.add_monitor,
            )
        )
        self.bot.add_handler(
            MessageHandler(
                ~filters.COMMAND
                & filters.Regex(self.actions_handler.strings.button.panel.settings),
                self.actions_handler.notifications,
            )
        )
        self.bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.actions_handler.user_message_handler))

    def run_polling(self) -> None:
        """
        Starting the bot's polling cycle.
        """
        self.bot.run_polling(allowed_updates=Update.ALL_TYPES)
