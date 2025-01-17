from homebot.core.config import get_config
from homebot.core.error_handler import format_exception
from homebot.core.logging import LOGE, LOGI
from homebot.modules.bridgey.platform import PlatformBase
from homebot.modules.bridgey.types.file import File
from homebot.modules.bridgey.types.message import Message, MessageType
from homebot.modules.bridgey.types.user import User
import requests
from telegram import File as TelegramFile
from telegram.bot import Bot
from telegram.error import BadRequest
from telegram.message import Message as TelegramMessage
from telegram.user import User as TelegramUser

ENABLE = get_config("bridgey.telegram.enable", False)
CHAT_ID = get_config("bridgey.telegram.chat_id", "")

posters: list[Bot] = []

class TelegramPlatform(PlatformBase):
	NAME = "Telegram"
	ICON_URL = "https://telegram.org/img/t_logo.png"
	FILE_TYPE = TelegramFile
	MESSAGE_TYPE = TelegramMessage
	USER_TYPE = TelegramUser

	@property
	def running(self) -> bool:
		return ENABLE and bool(CHAT_ID)

	def file_to_generic(self, file: FILE_TYPE) -> Message:
		return File(platform=TelegramPlatform,
		            url=file.file_path)

	def user_to_generic(self, user: USER_TYPE) -> User:
		try:
			user_propics = user.get_profile_photos().photos
		except BadRequest:
			user_propics = []

		if user_propics:
			avatar_url = user_propics[0][0].get_file().file_path
		else:
			avatar_url = ""

		return User(platform=TelegramPlatform,
		            name=user.full_name,
		            username=user.username,
		            avatar_url=avatar_url)

	def message_to_generic(self, message: MESSAGE_TYPE) -> Message:
		text = ""
		file = None
		sticker_emoji = ""
		if message.text:
			message_type = MessageType.TEXT
			text = message.text
		elif message.photo:
			message_type = MessageType.IMAGE
			text = message.caption
			file = message.photo[-1].get_file()
		elif message.video or message.animation:
			message_type = (MessageType.ANIMATION if message.animation else MessageType.VIDEO)
			text = message.caption
			file = (message.animation if message.animation else message.video).get_file()
		elif message.audio or message.voice:
			message_type = MessageType.AUDIO
			text = message.caption
			file = (message.voice if message.voice else message.audio).get_file()
		elif message.sticker:
			message_type = MessageType.STICKER
			file = message.sticker.thumb.get_file()
			sticker_emoji = message.sticker.emoji
		elif message.document:
			message_type = MessageType.DOCUMENT
			text = message.caption
			file = message.document.get_file()
		else:
			message_type = MessageType.UNKNOWN

		return Message(platform=TelegramPlatform,
		               message_type=message_type,
		               user=self.user_to_generic(message.from_user),
		               timestamp=message.date,
		               text=text if text else "",
		               file=self.file_to_generic(file) if file else None,
					   sticker_emoji=sticker_emoji)

	def send_message(self, message: Message) -> None:
		text = f"[{message.platform.NAME}] {message.user}:"
		if message.text:
			text += f"\n{message.text}"

		if message.file:
			try:
				r = requests.get(message.file.url)
			except Exception as e:
				LOGE(f"Failed to download file: {e}")
				return

		for bot in posters:
			try:
				if message.message_type == MessageType.TEXT:
					bot.send_message(chat_id=CHAT_ID, text=text)
				elif message.message_type == MessageType.IMAGE:
					bot.send_photo(chat_id=CHAT_ID, photo=r.content, filename=message.file.name, caption=text)
				elif message.message_type == MessageType.VIDEO:
					bot.send_video(chat_id=CHAT_ID, video=r.content, filename=message.file.name, caption=text)
				elif message.message_type == MessageType.AUDIO:
					bot.send_audio(chat_id=CHAT_ID, audio=r.content, filename=message.file.name, caption=text)
				elif message.message_type == MessageType.DOCUMENT:
					bot.send_document(chat_id=CHAT_ID, document=r.content, filename=message.file.name, caption=text)
				elif message.message_type == MessageType.STICKER:
					bot.send_sticker(chat_id=CHAT_ID, sticker=r.content)
				elif message.message_type == MessageType.ANIMATION:
					bot.send_animation(chat_id=CHAT_ID, animation=r.content, filename=message.file.name, caption=text)
				else:
					LOGI(f"Unknown message type: {message.message_type}")
			except Exception as e:
				LOGI(f"Failed to send message: {format_exception(e)}, retrying with different bot")
				print(message.file_url)
				continue

			break
