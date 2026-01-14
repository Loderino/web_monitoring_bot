import math
import asyncio
import json
from collections import defaultdict

from telegram.ext import Application
from telegram import (
    BotCommand,
    BotCommandScopeChat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot import ITEMS_PER_PAGE, MONITORING_INTERVALS
from bot.language import Language
from bot.models import NewMonitorTask, ModifyMonitorTask
from bot.url_validator import URLValidator
from constants import LANGUAGE_PATH
from db.db_handler import DBHandler
from task_manager import HTTPRequestor
from task_manager.models import Notification
from utils.classes import Observer
from utils.enums import ResponseStatus, SiteStatus
from utils.functions import format_duration
from utils.log import get_logger


class TGHandler(Observer):
    """
    Telegram Bot handler.

    This class contains all the commands and message handlers for the Telegram Bot.
    """

    users_tasks = {}
    messages_to_delete = defaultdict(list)

    def __init__(self, event_source, bot):
        """
        Initialize the Telegram Bot handler.

        Loads the language strings from a json file.
        """
        self.bot: Application = bot
        self._logger = get_logger("TGHandler")
        event_source.subscribe(self)
        self.url_validator = URLValidator()
        self.db = DBHandler()
        self.requestor = HTTPRequestor()
        with open(LANGUAGE_PATH, encoding="utf-8") as f:
            self.strings: Language = Language.from_dict(  # pylint: disable=no-member
                json.load(f)
            )

    async def _delete_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Deletes a message from the chat.

        Args:
            update (Update): The update object containing information about the message.
            context (ContextTypes.DEFAULT_TYPE): The context object.
        """
        for message in self.messages_to_delete[update.effective_user.id]:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=message.message_id,
                )
                self.messages_to_delete.pop(update.effective_user.id)
            except (TelegramError, KeyError):
                pass

    async def notify(self, notification: Notification):
        """
        Asynchronously notifies the observer about some events.

        Args:
            notification: some notification object.

        Returns:
            Any: The result of the notification processing.
        """
        url = notification.url
        status = notification.status

        users_ids = await self.db.get_monitor_users_by_url(url)
        users = await asyncio.gather(*[self.db.get_user(user_id) for user_id in users_ids])
        for user in users:
            if user is not None:
                if status == SiteStatus.AVAILABLE:
                    if user.site_recovery_notifications:
                        try:
                            await self.bot.send_message(user._id, f"{url} заработал")
                        except:
                            self._logger.warning("Error when attempt to send notification to user %d", user._id, exc_info=True)    
                        self._logger.info("User %d gets notification %s", user._id, str(notification))
                        continue
                if status == SiteStatus.UNAVAILABLE:
                    if user.site_crash_notifications:
                        try:
                            await self.bot.send_message(user._id, f"{url} упал")
                        except:
                            self._logger.warning("Error when attempt to send notification to user %d", user._id, exc_info=True)
                        self._logger.info("User %d gets notification %s", user._id, str(notification))

    # Command handlers

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Start command handler.

        Set the commands for the chat and send a welcome message.
        """
        if update.effective_chat.type in ("group", "supergroup"):
            return

        await self._delete_messages(update, context)
        user_id = update.effective_chat.id
        await context.bot.set_my_commands(
            [
                BotCommand("/help", self.strings.help_command_description),
                BotCommand("/monitors", self.strings.monitors_command_description),
            ],
            scope=BotCommandScopeChat(chat_id=user_id),
        )
        buttons = self.strings.button.panel
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [buttons.my_monitors, buttons.add_monitor],
                [buttons.settings, buttons.statistics],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=self.strings.start_command_answer,
            reply_markup=keyboard,
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Help command handler.

        Send a message with the bot abilities.
        """
        if update.effective_chat.type in ("group", "supergroup"):
            return
        await self._delete_messages(update, context)
        text = self.strings.help_command_answer
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    async def monitors(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1
    ) -> None:
        """
        Monitors command handler.

        Send a message with the user's monitors list.
        """
        if update.effective_chat.type in ("group", "supergroup"):
            return
        await self._delete_messages(update, context)
        user_id = update.effective_chat.id
        text=""
        monitors_count = await self.db.get_user_monitors_count(user_id)
        if monitors_count is None:
            await context.bot.send_message(user_id, self.strings.some_error)
            return
        total_pages = math.ceil(monitors_count / ITEMS_PER_PAGE)
        if page > total_pages:
            page = total_pages
        if page < 1:
            page = 1
        monitors = await self.db.get_user_monitors(
            user_id,
            skip=(page-1)*ITEMS_PER_PAGE,
            limit=ITEMS_PER_PAGE
        )
        if monitors is None:
            text = self.strings.some_error
            await context.bot.send_message(user_id, text)
        elif not monitors:
            text = "📊 Мои мониторы\n\nУ вас пока нет активных мониторов.\n\nНажмите `➕ Добавить монитор` для создания первого."
            await context.bot.send_message(user_id, text)
        else:
            keyboard = []
            monitored_sites = await asyncio.gather(*[self.db.get_site(monitor.url) for monitor in monitors])
            text = f"📊 Мои мониторы (стр. {page}/{total_pages})\n\n"

            for idx, monitor in enumerate(monitors, (page-1)*ITEMS_PER_PAGE+1):
                if monitored_sites[(idx-1)%ITEMS_PER_PAGE]:
                    if monitored_sites[(idx-1)%ITEMS_PER_PAGE].status == SiteStatus.AVAILABLE:
                        circle = "🟢"
                    else:
                        circle = "🔴"
                else:
                    circle = "🔴"
                text += f"#{idx} {circle} {monitor.url} ⏳{format_duration(monitor.interval)}\n"
                keyboard.append([
                    InlineKeyboardButton(f"⚙️ #{idx}", callback_data=f"monitors_modify_{idx-1}"),
                    InlineKeyboardButton(f"🗑 #{idx}", callback_data=f"monitors_delete_{idx-1}")
                ])

            arrows_buttons = []
            if page > 1:
                arrows_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"monitors_list_{page-1}"))
            if page < total_pages:
                arrows_buttons.append(InlineKeyboardButton("➡️", callback_data=f"monitors_list_{page+1}"))
            if arrows_buttons:
                keyboard.append(arrows_buttons)
            self.messages_to_delete[user_id].append(
                await context.bot.send_message(user_id, text, reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True))

    async def add_monitor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Add monitor command handler.

        Send a message with the user's monitors list.
        """
        await self._delete_messages(update, context)
        if update.effective_chat.type in ("group", "supergroup"):
            return
        user_id = update.effective_chat.id
        if user_id not in self.users_tasks:
            self.users_tasks[user_id] = NewMonitorTask()

        monitor_url = (
            self.users_tasks[user_id].url
            if self.users_tasks[user_id].url
            else self.strings.not_defined
        )
        monitor_interval = (
            format_duration(self.users_tasks[user_id].interval)
            if self.users_tasks[user_id].interval
            else self.strings.not_defined
        )
        text = self.strings.new_monitor_task_status.format(monitor_url, monitor_interval)

        buttons = self.strings.button.inline

        keyboard = [
            [
                InlineKeyboardButton(
                    buttons.insert_url, callback_data="new-monitor_url_"
                )
            ],
            [
                InlineKeyboardButton(
                    buttons.select_interval, callback_data="new-monitor_interval_"
                )
            ],
            [InlineKeyboardButton(buttons.cancel, callback_data="new-monitor_cancel_")],
        ]
        if self.users_tasks[user_id].interval and self.users_tasks[user_id].url:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        buttons.finish, callback_data="new-monitor_finish_"
                    )
                ]
            )
        await context.bot.send_message(
            chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True
        )

    async def notifications(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._delete_messages(update, context)
        user_id = update.effective_chat.id
        user_info = await self.db.get_user(user_id=user_id)
        if user_info is None:
            await context.bot.send_message(user_id, self.strings.some_error)
            return
        if not user_info:
            user_info = await self.db.add_user(user_id)
            if user_info is None:
                await context.bot.send_message(user_id, self.strings.some_error)
                return

        crash_n = user_info.site_crash_notifications
        recovery_n = user_info.site_recovery_notifications
        weekly_n = user_info.weekly_report_notifications
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"1️⃣ {'Выключить' if crash_n else 'Включить'}", callback_data=f"notifications_crash_{not crash_n}")],
            [InlineKeyboardButton(f"2️⃣ {'Выключить' if recovery_n else 'Включить'}", callback_data=f"notifications_recovery_{not recovery_n}")],
            [InlineKeyboardButton(f"3️⃣ {'Выключить' if weekly_n else 'Включить'}", callback_data=f"notifications_weekly_{not weekly_n}")],
        ])

        self.messages_to_delete[user_id].append(await context.bot.send_message(
            user_id, 
            text=self.strings.notifications_settings.format(
                "✅" if crash_n else "❌",
                "✅" if recovery_n else "❌",
                "✅" if weekly_n else "❌"
                ),
            reply_markup=keyboard))


    async def user_message_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handler for users text messages.
        """
        if update.effective_chat.type in ("group", "supergroup"):
            return
        await self._delete_messages(update, context)
        user_id = update.effective_user.id
        if self.users_tasks.get(user_id, None):
            user_task = self.users_tasks[update.effective_user.id]
            match user_task:
                case NewMonitorTask() if user_task.is_url_expected:
                    url = update.message.text
                    is_valid, description = self.url_validator.validate_url(url)
                    if is_valid:
                        if await self.db.check_user_monitors_for_url(user_id, url):
                            await context.bot.send_message(user_id, self.strings.new_monitor_existing_url)
                            return
                        self.users_tasks[update.effective_user.id].url = url
                        self.users_tasks[user_id].is_url_expected = False
                        await self.add_monitor(update, context)
                    else:
                        text = self.strings.new_monitor_wrong_url.format(description)
                        await context.bot.send_message(user_id, text)


    # callback handlers
    async def handle_buttons(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle button press events.
        """
        user_id = update.effective_user.id
        query = update.callback_query

        callback_msg = query.data
        task, parameter, value = callback_msg.split("_")
        match task:
            case "new-monitor":
                await query.answer()
                match parameter:
                    case "url":
                        self.users_tasks[user_id].is_url_expected = True
                        await query.edit_message_text(
                            text="Введите URL", reply_markup=None
                        )

                    case "interval":
                        text = "Выберите интервал"
                        keyboard = InlineKeyboardMarkup(
                            [
                                [
                                    InlineKeyboardButton(
                                        f"⏳ {format_duration(seconds, full_words=True)}",
                                        callback_data=f"new-monitor_interval-time_{seconds}",
                                    )
                                ]
                                for seconds in MONITORING_INTERVALS
                            ]
                        )
                        await query.edit_message_text(text=text, reply_markup=keyboard)
                    case "interval-time":
                        self.users_tasks[user_id].interval = int(value)
                        await query.message.delete()
                        await self.add_monitor(update, context)

                    case "cancel":
                        self.users_tasks.pop(update.effective_user.id)
                        await query.message.delete()

                    case "finish":
                        task: NewMonitorTask = self.users_tasks.pop(user_id, None)
                        if task:
                            response_data = await self.requestor.make_request(task.url)
                            site_status = (
                                SiteStatus.AVAILABLE
                                if response_data.status == ResponseStatus.OK
                                else SiteStatus.UNAVAILABLE
                            )
                            if await self.db.get_site(task.url) is None:
                                if not await self.db.add_site(task.url, site_status.value):
                                    self._logger.warning(
                                        "Error writing the site %s to the database.",
                                        task.url,
                                    )
                            if not await self.db.add_monitor(
                                user_id, task.url, task.interval
                            ):
                                self._logger.error(
                                    "Error writing the monitor (url: %s, interval: %s) to the database for user %d",
                                    task.url,
                                    task.interval,
                                    user_id,
                                )
                                self.users_tasks[user_id] = task
                                await query.edit_message_text(
                                    text=self.strings.some_error, reply_markup=None)
                            else:
                                self._logger.info(
                                    "User %d adds monitor %s with interval %s",
                                    user_id,
                                    task.url,
                                    task.interval,
                                )
                                await query.edit_message_text(
                                    text=self.strings.new_monitor_task_success, reply_markup=None)
                            if not await self.db.add_check_record(
                                response_data.prepare_for_database()
                            ):
                                self._logger.warning(
                                    "Error writing the check %s to the database.",
                                    response_data.prepare_for_database(),
                                )
            case "monitors":
                match parameter:
                    case "list":
                        await query.delete_message()
                        await self.monitors(update, context, int(value))
                    
                    case "delete":
                        monitor = (await self.db.get_user_monitors(user_id, skip=int(value), limit=1))[0]
                        if monitor:
                            if await self.db.delete_monitor(user_id, monitor.url):
                                query.answer(
                                    text=self.strings.delete_monitor_success.format(monitor.url),
                                    show_alert=True
                                )
                            else:
                                query.answer(
                                text=self.strings.some_error,
                                show_alert=True
                            )
                        else:
                            query.answer(
                                text=self.strings.some_error,
                                show_alert=True
                            )
                        await query.delete_message()
                        await self.monitors(update, context, page = math.floor(int(value)/ITEMS_PER_PAGE)+1)
                    
                    case "modify":
                        # await query.delete_message()
                        self.users_tasks[user_id] = ModifyMonitorTask(int(value))
                        text = "Выберите интервал"
                        keyboard = InlineKeyboardMarkup(
                            [
                                [
                                    InlineKeyboardButton(
                                        f"⏳ {format_duration(seconds, full_words=True)}",
                                        callback_data=f"monitors_interval-time_{seconds}",
                                    )
                                ]
                                for seconds in MONITORING_INTERVALS
                            ]
                        )
                        await query.edit_message_text(text=text, reply_markup=keyboard)
                    
                    case "interval-time":
                        seconds = int(value)
                        task = self.users_tasks[user_id]
                        monitor = (await self.db.get_user_monitors(user_id, skip=task.index, limit=1))[0]
                        if monitor:
                            if await self.db.update_monitor(user_id, monitor.url, seconds):
                                await query.answer(
                                text=self.strings.update_monitor_success.format(monitor.url),
                                show_alert=True
                            )
                            else:
                                await query.answer(
                                text=self.strings.some_error,
                                show_alert=True
                            )
                        else:
                            await query.answer(
                                text=self.strings.some_error,
                                show_alert=True
                            )
                        await query.delete_message()
                        await self.monitors(update, context, page = math.floor(int(value)/ITEMS_PER_PAGE)+1)
            
            case "notifications":
                match parameter:
                    case "crash":
                        if value == "True":
                            result = await self.db.update_user(user_id, crash_n=True)
                        else:
                            result = await self.db.update_user(user_id, crash_n=False)
                        if result:
                            await query.answer(self.strings.successful_changes, show_alert=True)
                        else:
                            await query.answer(self.strings.some_error, show_alert=True)
                    case "recovery":
                        if value == "True":
                            result = await self.db.update_user(user_id, recovery_n=True)
                        else:
                            result = await self.db.update_user(user_id, recovery_n=False)
                        if result:
                            await query.answer(self.strings.successful_changes, show_alert=True)
                        else:
                            await query.answer(self.strings.some_error, show_alert=True)
                    case "weekly":
                        if value == "True":
                            result = await self.db.update_user(user_id, weekly_n=True)
                        else:
                            result = await self.db.update_user(user_id, weekly_n=False)
                        if result:
                            await query.answer(self.strings.successful_changes, show_alert=True)
                        else:
                            await query.answer(self.strings.some_error, show_alert=True)

                await self.notifications(update, context)