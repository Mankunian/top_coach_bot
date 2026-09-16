import os
from .service import telegram

if __name__ == '__main__':
    url = os.environ['PUBLIC_URL'].rstrip('/')
    if not url.startswith('https://'):
        raise SystemExit('PUBLIC_URL must use HTTPS')
    telegram('setMyDescription', {'description': '🎾 TopCoach — помощник теннисного тренера и игрока. Регистрация, профиль и быстрый доступ к Mini App.'})
    telegram('setMyShortDescription', {'short_description': '🎾 Ваш теннис — в одном приложении.'})
    telegram('setMyCommands', {'commands': [{'command': 'start', 'description': '🎾 Открыть TopCoach / регистрация'}]})
    telegram('setChatMenuButton', {'menu_button': {'type': 'web_app', 'text': '🎾 TopCoach', 'web_app': {'url': os.environ['MINI_APP_URL']}}})
    telegram('setWebhook', {'url': url + '/telegram/webhook', 'secret_token': os.environ['WEBHOOK_SECRET'], 'allowed_updates': ['message', 'callback_query']})
    print('Bot descriptions, menu and webhook configured')
