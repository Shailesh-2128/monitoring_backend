import json
import logging
import urllib.request
import urllib.parse
from django.utils import timezone
from .models import TelegramConfig, TelegramSubscriber, TelegramNotificationLog

logger = logging.getLogger(__name__)


class TelegramService:

    @staticmethod
    def get_token():
        config = TelegramConfig.get_config()
        return config.bot_token

    @staticmethod
    def send_message(chat_id: str, text: str, parse_mode: str = 'HTML') -> tuple[bool, str]:
        """
        Sends message to a Telegram chat using Telegram Bot API.
        """
        token = TelegramService.get_token()
        if not token:
            return False, "Telegram Bot Token is not configured."

        if not chat_id:
            return False, "Chat ID is missing."

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res_body = json.loads(response.read().decode())
                if res_body.get('ok'):
                    return True, "Message sent successfully"
                else:
                    err_msg = res_body.get('description', 'Unknown error')
                    return False, f"Telegram API error: {err_msg}"
        except Exception as e:
            logger.exception("Error sending Telegram message")
            return False, str(e)

    @staticmethod
    def process_telegram_update(update_data: dict) -> dict:
        """
        Processes an incoming update object from Telegram (from webhook or getUpdates).
        Checks if update has a text message starting with '/start'.
        """
        message = update_data.get('message') or update_data.get('edited_message')
        if not message:
            return {"status": "ignored", "reason": "No message object"}

        chat = message.get('chat', {})
        chat_id = str(chat.get('id', ''))
        user_from = message.get('from', {})
        username = user_from.get('username', '') or chat.get('username', '')
        first_name = user_from.get('first_name', '') or chat.get('first_name', '')
        last_name = user_from.get('last_name', '') or chat.get('last_name', '')
        text = (message.get('text') or '').strip()

        if not text:
            return {"status": "ignored", "reason": "Empty text"}

        # Handle /start or /start <token>
        if text.startswith('/start'):
            parts = text.split(maxsplit=1)
            token_param = parts[1].strip() if len(parts) > 1 else ''

            subscriber = None
            if token_param:
                subscriber = TelegramSubscriber.objects.filter(verification_token=token_param).first()

            # If token matched or subscriber already linked to this chat_id
            if not subscriber and chat_id:
                subscriber = TelegramSubscriber.objects.filter(chat_id=chat_id).first()

            if subscriber:
                subscriber.chat_id = chat_id
                subscriber.telegram_username = username
                subscriber.first_name = first_name
                subscriber.last_name = last_name
                subscriber.is_verified = True
                subscriber.connected_at = timezone.now()
                subscriber.save()

                welcome_msg = (
                    f"🟢 <b>Telegram Connected Successfully!</b>\n\n"
                    f"Hello <b>{first_name or username or 'User'}</b>,\n"
                    f"Your Telegram account (<code>@{username or chat_id}</code>) is now linked to <b>DeployOps Monitoring Suite</b>.\n\n"
                    f"⚡ <i>You will receive real-time Server Overload alerts and GitHub push notifications directly in this chat!</i>"
                )
                TelegramService.send_message(chat_id, welcome_msg)

                # Log confirmation
                TelegramNotificationLog.objects.create(
                    subscriber=subscriber,
                    chat_id=chat_id,
                    notification_type='SYSTEM',
                    title='Telegram Connection Verified',
                    message=welcome_msg,
                    status='SENT'
                )

                return {
                    "status": "connected",
                    "subscriber_id": subscriber.id,
                    "chat_id": chat_id,
                    "username": username
                }
            else:
                # Unrecognized start command, send connection instruction
                reply = (
                    "ℹ️ <b>DeployOps Monitoring Bot</b>\n\n"
                    "To link your Telegram account, please click <b>[ Connect Telegram ]</b> inside your DeployOps Monitoring dashboard and follow the link!"
                )
                TelegramService.send_message(chat_id, reply)
                return {"status": "unverified", "chat_id": chat_id}

        return {"status": "processed", "text": text}

    @staticmethod
    def sync_updates() -> dict:
        """
        Polls getUpdates from Telegram API to process incoming updates (useful for local dev without webhooks).
        """
        config = TelegramConfig.get_config()
        token = config.bot_token
        if not token:
            return {"ok": False, "error": "Bot token not configured"}

        url = f"https://api.telegram.org/bot{token}/getUpdates?offset={config.last_update_id + 1}&timeout=2"
        processed_count = 0

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                if data.get('ok'):
                    results = data.get('result', [])
                    for update in results:
                        update_id = update.get('update_id')
                        if update_id and update_id > config.last_update_id:
                            config.last_update_id = update_id
                        TelegramService.process_telegram_update(update)
                        processed_count += 1
                    
                    config.save(update_fields=['last_update_id'])
                    return {"ok": True, "processed": processed_count}
                else:
                    return {"ok": False, "error": data.get('description')}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def send_server_overload_alert(server, reading, overload_reasons: list[str]) -> int:
        """
        Formats and dispatches server overload alert to all active verified subscribers.
        """
        config = TelegramConfig.get_config()
        if not config.notify_server_overload:
            return 0

        reasons_text = "\n".join([f"• ⚠️ <b>{r}</b>" for r in overload_reasons])
        
        msg = (
            f"🚨 <b>SERVER OVERLOAD ALERT</b> 🚨\n\n"
            f"🖥️ <b>Server:</b> {server.name} (ID: <code>{server.id}</code>)\n"
            f"📁 <b>Project:</b> {server.project_name}\n"
            f"🌐 <b>Hostname / IP:</b> {server.hostname} ({server.public_ip or 'N/A'})\n"
            f"🏷️ <b>Environment:</b> {server.environment}\n\n"
            f"📊 <b>Resource Usage:</b>\n"
            f"• <b>CPU:</b> {reading.cpu:.1f}%\n"
            f"• <b>RAM:</b> {reading.ram:.1f}%\n"
            f"• <b>Disk:</b> {reading.disk:.1f}%\n"
            f"• <b>Load Avg (1m):</b> {reading.load_average_1m:.2f}\n\n"
            f"🔍 <b>Triggered Warnings:</b>\n"
            f"{reasons_text}\n\n"
            f"⏰ <i>Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
        )

        subscribers = TelegramSubscriber.objects.filter(is_verified=True, notifications_enabled=True).exclude(chat_id='')
        sent_count = 0

        for sub in subscribers:
            success, err = TelegramService.send_message(sub.chat_id, msg)
            TelegramNotificationLog.objects.create(
                subscriber=sub,
                chat_id=sub.chat_id,
                notification_type='SERVER_OVERLOAD',
                title=f"Server Overload: {server.name}",
                message=msg,
                status='SENT' if success else 'FAILED',
                error_message='' if success else err
            )
            if success:
                sent_count += 1

        return sent_count

    @staticmethod
    def send_github_push_alert(repo_name: str, branch: str, pusher: str, commits: list, commit_url: str = '') -> int:
        """
        Formats and dispatches GitHub Push notification to all verified subscribers.
        """
        config = TelegramConfig.get_config()
        if not config.notify_github_push:
            return 0

        commit_lines = []
        for c in commits[:5]:  # Limit to 5 commits preview
            msg = c.get('message', '').split('\n')[0]
            sha = c.get('id', '')[:7]
            commit_lines.append(f"• <code>{sha}</code> - {msg}")

        commits_text = "\n".join(commit_lines) if commit_lines else "• New push committed"

        msg = (
            f"🚀 <b>NEW GITHUB PUSH DETECTED</b>\n\n"
            f"📦 <b>Repository:</b> <code>{repo_name}</code>\n"
            f"🌿 <b>Branch:</b> <code>{branch}</code>\n"
            f"👤 <b>Pushed By:</b> {pusher}\n\n"
            f"📝 <b>Commits ({len(commits)}):</b>\n"
            f"{commits_text}\n\n"
        )
        if commit_url:
            msg += f"🔗 <a href='{commit_url}'>View Push Details on GitHub</a>\n\n"

        msg += f"⏰ <i>Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"

        subscribers = TelegramSubscriber.objects.filter(is_verified=True, notifications_enabled=True).exclude(chat_id='')
        sent_count = 0

        for sub in subscribers:
            success, err = TelegramService.send_message(sub.chat_id, msg)
            TelegramNotificationLog.objects.create(
                subscriber=sub,
                chat_id=sub.chat_id,
                notification_type='GITHUB_PUSH',
                title=f"GitHub Push: {repo_name} ({branch})",
                message=msg,
                status='SENT' if success else 'FAILED',
                error_message='' if success else err
            )
            if success:
                sent_count += 1

        return sent_count

    @staticmethod
    def send_database_backup_alert(database, action_type: str, file_name: str, file_size_str: str = "", username: str = "Admin", is_success: bool = True, error_msg: str = "") -> int:
        """
        Dispatches database backup export or import notification to active verified Telegram subscribers.
        action_type: 'EXPORT' or 'IMPORT'
        """
        config = TelegramConfig.get_config()
        if not getattr(config, 'notify_database_backup', True):
            return 0

        now_str = timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        if action_type.upper() == 'EXPORT':
            header = "💾 <b>DATABASE BACKUP GENERATED</b> 💾"
            action_desc = "Exported / Downloaded SQL Backup"
        else:
            header = "📥 <b>DATABASE BACKUP RESTORED</b> 📥"
            action_desc = "Imported / Restored SQL Backup"

        status_str = "✅ <b>SUCCESS</b>" if is_success else "❌ <b>FAILED</b>"

        msg = (
            f"{header}\n\n"
            f"📁 <b>Project:</b> {database.project}\n"
            f"🗄️ <b>Database Name:</b> {database.name} (<code>{database.database_name or 'default'}</code>)\n"
            f"🏷️ <b>Engine:</b> {database.db_type}\n"
            f"🌐 <b>Host:</b> <code>{database.host}:{database.port}</code>\n"
            f"⚡ <b>Action:</b> {action_desc}\n"
            f"📄 <b>File:</b> <code>{file_name}</code>"
        )
        if file_size_str:
            msg += f" ({file_size_str})"
        msg += f"\n📊 <b>Status:</b> {status_str}\n"
        msg += f"👤 <b>Triggered By:</b> {username}\n"

        if not is_success and error_msg:
            msg += f"\n⚠️ <b>Error Details:</b>\n<code>{error_msg[:300]}</code>\n"

        msg += f"\n⏰ <i>Time: {now_str}</i>"

        subscribers = TelegramSubscriber.objects.filter(is_verified=True, notifications_enabled=True).exclude(chat_id='')
        sent_count = 0

        for sub in subscribers:
            success, err = TelegramService.send_message(sub.chat_id, msg)
            TelegramNotificationLog.objects.create(
                subscriber=sub,
                chat_id=sub.chat_id,
                notification_type='DATABASE_BACKUP',
                title=f"Database Backup {action_type.title()}: {database.name}",
                message=msg,
                status='SENT' if success else 'FAILED',
                error_message='' if success else err
            )
            if success:
                sent_count += 1

        return sent_count

