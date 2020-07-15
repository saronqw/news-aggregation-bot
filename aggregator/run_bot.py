import json
import logging
import os
import sys
from threading import Thread

import time
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, \
    ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, \
    ConversationHandler, MessageHandler, Filters

from aggregator.model.news_item import NewsItem
from pagination import InlineKeyboardPaginator

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Stages
MENU_STATE, NEWS_STATE, TRENDS_STATE, CHARTS_STATE, TYPING = map(chr, range(5))
# Callback data
NEWS, TRENDS, CHARTS = map(chr, range(3))
UNIVERSITY, ONE_UNIVERSITY, INTERVAL, FAIL_INTERVAL = map(chr, range(3, 7))
MENU = "menu"
ALL_UNIVERSITIES = "all"
ONE_DAY = "one_day"
THREE_DAYS = "three_days"
SEVEN_DAYS = "seven_days"
list_news_items = []
count_pages = 0


def start_command(update, context):
    button_list = [
        InlineKeyboardButton(text="News 📚", callback_data=str(NEWS)),
        InlineKeyboardButton(text="Trends 🏆", callback_data=str(TRENDS)),
        InlineKeyboardButton(text="Сharts 📈", callback_data=str(CHARTS))
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=1))

    update.message.reply_text(
        text="Hello! 🤓\n" +
             "Are you interested in news of the leading universities in the world?\n" +
             "I can help you! 👻\n" +
             "Choose one of the proposed options:",
        reply_markup=reply_markup
    )
    return MENU_STATE


def menu(update, context):
    query = update.callback_query
    query.answer()
    button_list = [
        InlineKeyboardButton(text="News 📚", callback_data=str(NEWS)),
        InlineKeyboardButton(text="Trends 🏆", callback_data=str(TRENDS)),
        InlineKeyboardButton(text="Сharts 📈", callback_data=str(CHARTS))
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=1))

    query.edit_message_text(
        text="Hello! 🤓\n" +
             "Are you interested in news of the leading universities in the world?\n" +
             "I can help you! 👻\n" +
             "Choose one of the proposed options:",
        reply_markup=reply_markup
    )
    return MENU_STATE


def help_command(update, context):
    update.message.reply_text('Help!')


def build_menu(buttons,
               n_cols,
               header_buttons=None,
               footer_buttons=None):
    new_menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        new_menu.insert(0, [header_buttons])
    if footer_buttons:
        new_menu.append([footer_buttons])
    return new_menu


def unknown(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I didn't understand that command.")


def news(update, context):
    context.user_data[UNIVERSITY] = None
    context.user_data[INTERVAL] = None
    query = update.callback_query
    query.answer()
    keyboard = [
        InlineKeyboardButton("All universities 🕍", callback_data=str(ALL_UNIVERSITIES)),
        InlineKeyboardButton("Type name university 📝", callback_data=str(ONE_UNIVERSITY))
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(keyboard, n_cols=1))

    query.edit_message_text(
        text="📚 What universities are you interested in? \n"
             "Choose one of the proposed options:",
        reply_markup=reply_markup
    )
    return NEWS_STATE


def interval(update, context):
    query = update.callback_query
    keyboard = [
        InlineKeyboardButton("1 Day", callback_data=str(ONE_DAY)),
        InlineKeyboardButton("3 Days", callback_data=str(THREE_DAYS)),
        InlineKeyboardButton("7 Days", callback_data=str(SEVEN_DAYS))
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(keyboard, n_cols=1))

    text = "💬 How long do you want to see the news?\n" \
           + "Choose one of the proposed options:"

    if str(update.callback_query.data) != str(FAIL_INTERVAL):
        context.user_data[UNIVERSITY] = update.callback_query.data

    if update.callback_query.data == 'all' or update.callback_query.data == str(FAIL_INTERVAL):
        query.answer()
        query.edit_message_text(
            text=text,
            reply_markup=reply_markup
        )
    else:
        update.message.reply_text(
            text=text,
            reply_markup=reply_markup
        )

    return NEWS_STATE


def news_request(update, context):
    def object_decoder(obj):
        return NewsItem(obj['title'], obj['description'], obj['link'], obj['pub_date'])

    # MEMORY VARIABLES
    context.user_data[INTERVAL] = update.callback_query.data
    name = context.user_data[UNIVERSITY]

    interval_time = context.user_data[INTERVAL]

    # REQUEST
    r = requests.get('http://192.168.0.25/api/v1/rest_api/lastnews/?interval=' + interval_time + "&name=" + name)
    data = json.dumps(r.json(), ensure_ascii=False, indent=4)

    if data == '[]':
        update.callback_query.data = str(FAIL_INTERVAL)
        interval_error(update, context)
        return False

    # unicode(data)
    # RESULT IN LIST
    result = json.loads(data,
                        object_hook=object_decoder)
    list_news_items.clear()
    for news_item in result:
        temp_word_list = news_item.description.split(" ")[:18]

        description = ""
        for word in temp_word_list:
            description += word + " "

        list_news_items.append("🔸 *" + news_item.title + "*" + "\n"
                               + description.rstrip() + "...\n"
                               + "_Link:_ [show details](" + news_item.link + ")")
    return True


def show_news(update, context):
    if not news_request(update, context):
        return NEWS_STATE

    query = update.callback_query
    query.answer()

    # PAGINATION
    length = len(list_news_items)
    if length % 3 == 0:
        global count_pages
        count_pages = int(length / 3)
    else:
        count_pages = int(length / 3) + 1

    paginator = InlineKeyboardPaginator(
        count_pages,
        data_pattern='character#{page}'
    )
    query.edit_message_text(
        text="\n\n".join(list_news_items[:3]),
        reply_markup=paginator.markup,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

    return NEWS_STATE


def characters_page_callback(update, context):
    query = update.callback_query

    query.answer()

    page = int(query.data.split('#')[1])

    paginator = InlineKeyboardPaginator(
        count_pages,
        current_page=page,
        data_pattern='character#{page}'
    )

    left_border = (page - 1) * 3
    right_border = (page - 1) * 3 + 3
    length = len(list_news_items)
    if right_border >= length:
        right_border = length

    query.edit_message_text(
        text="\n\n".join(list_news_items[left_border: right_border]),
        reply_markup=paginator.markup,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )


def choose_university(update, context):
    query = update.callback_query
    query.answer()

    query.edit_message_text(text='Enter university name')

    return TYPING


def save_input(update, context):
    context.user_data[UNIVERSITY] = update.message.text
    return interval(update, context)


def interval_error(update, context):
    query = update.callback_query
    query.answer()

    keyboard = [
        InlineKeyboardButton("Back", callback_data=str(FAIL_INTERVAL))
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(keyboard, n_cols=1))

    text = "😿 There is no news in this interval.\n" \
           + "Сome back, please, and select another one."

    query.edit_message_text(
        text=text,
        reply_markup=reply_markup
    )


def trends(update, context):
    query = update.callback_query
    query.answer()

    button_list = [
        InlineKeyboardButton(text="MENU", callback_data=str(MENU)),
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=1))

    text = '🤓 IT\'S TRENDS:\n`' \
           + ' 1. COVID19                  666\n' \
           + ' 2. BTS                      629\n' \
           + ' 3. LGBT                     433\n' \
           + ' 4. Last Of Us 2             325\n' \
           + ' 5. Пустые города            277\n' \
           + ' 6. 5G                       256\n' \
           + ' 7. Разумное потребление     128\n' \
           + ' 8. Искусственный интеллект   64\n' \
           + ' 9. Носки с сандалиями        32\n' \
           + '10. Big Data                  16`'

    query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

    return TRENDS_STATE


def charts(update, context):
    query = update.callback_query
    query.answer()

    button_list = [
        InlineKeyboardButton(text="MENU", callback_data=str(MENU)),
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=1))

    query.edit_message_text(
        text="It's Charts! 🤓\n",
        reply_markup=reply_markup
    )
    return CHARTS_STATE


def menu_command(update, context):
    start_command(update, context)
    return MENU_STATE


def trends_command(update, context):
    text = '🤓 IT\'S TRENDS:\n`' \
           + ' 1. COVID19                  666\n' \
           + ' 2. BTS                      629\n' \
           + ' 3. LGBT                     433\n' \
           + ' 4. Last Of Us 2             325\n' \
           + ' 5. Пустые города            277\n' \
           + ' 6. 5G                       256\n' \
           + ' 7. Разумное потребление     128\n' \
           + ' 8. Искусственный интеллект   64\n' \
           + ' 9. Носки с сандалиями        32\n' \
           + '10. Big Data                  16`'

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode=ParseMode.MARKDOWN
    )


def charts_command(update, context):
    text = "It's Charts! 🤓\n"

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode=ParseMode.MARKDOWN
    )


def main(token):
    updater = Updater(token, use_context=True)
    dispatcher = updater.dispatcher

    def stop_and_restart():
        """Gracefully stop the Updater and replace the current process with a new one"""
        updater.stop()
        os.execl(sys.executable, sys.executable, *sys.argv)

    def restart(update, context):
        update.message.reply_text('Bot is restarting...')
        Thread(target=stop_and_restart).start()
        time.sleep(2)
        context.bot.send_message(chat_id=update.effective_chat.id, text="Done!")

    start_handler = CommandHandler('start', start_command)
    menu_handler = CommandHandler('menu', menu_command)

    conversation_handler = ConversationHandler(
        entry_points=[start_handler, menu_handler],
        states={
            NEWS_STATE: [
                CallbackQueryHandler(interval, pattern='^' + str(ALL_UNIVERSITIES) + '$'),
                CallbackQueryHandler(menu, pattern='^' + str(ONE_UNIVERSITY) + '$'),
                CallbackQueryHandler(show_news,
                                     pattern='^' + str(ONE_DAY) + '$|' +
                                             '^' + str(THREE_DAYS) + '$|' +
                                             '^' + str(SEVEN_DAYS) + '$'),
                CallbackQueryHandler(characters_page_callback, pattern='^character#'),
                CallbackQueryHandler(interval, pattern='^' + str(FAIL_INTERVAL) + '$'),
                CallbackQueryHandler(menu, pattern='^' + str(MENU) + '$'),
            ],
            TRENDS_STATE: [
                CallbackQueryHandler(menu, pattern='^' + str(MENU) + '$'),
            ],
            CHARTS_STATE: [
                CallbackQueryHandler(menu, pattern='^' + str(MENU) + '$'),
            ],
            MENU_STATE: [
                CallbackQueryHandler(news, pattern='^' + str(NEWS) + '$'),
                CallbackQueryHandler(trends, pattern='^' + str(TRENDS) + '$'),
                CallbackQueryHandler(charts, pattern='^' + str(CHARTS) + '$')
            ],
            TYPING: [MessageHandler(Filters.text, save_input)],
        },
        fallbacks=[
            # start_handler,
            menu_handler,
            CommandHandler('restart', restart, filters=Filters.user(username=['@saronqw', '@gilevAn'])),
            CommandHandler('trends', trends_command),
            CommandHandler('charts', charts_command)
        ]
    )

    dispatcher.add_handler(CommandHandler('help', help_command))
    dispatcher.add_handler(conversation_handler)
    dispatcher.add_handler(CommandHandler('restart', restart, filters=Filters.user(username=['@saronqw', '@gilevAn'])))
    updater.start_polling()
    updater.idle()
