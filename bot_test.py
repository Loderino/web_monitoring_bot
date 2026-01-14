from bot.tg_bot import TGBot

def main():
    bot = TGBot()
    bot.run_polling()  # Без asyncio.run и await

if __name__ == "__main__":
    main()
