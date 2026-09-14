import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import yfinance as yf
from apscheduler.schedulers.background import BackgroundScheduler

# Konfigurasi Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Token Bot Telegram dari BotFather
TOKEN = "TOKENDISINIII"

# Penyimpanan memori sementara dengan struktur list agar memiliki nomor urut (ID)
# Format: {chat_id: [{'ticker': 'BUMI', 'target': 576}, {'ticker': 'TLKM', 'target': 3500}]}
watchlist = {}


def get_realtime_price(ticker_symbol: str) -> float:
    """Mengambil harga real-time dari Yahoo Finance dengan ekstensi .JK untuk saham Indonesia."""
    try:
        formatted_ticker = ticker_symbol.upper()
        if not formatted_ticker.endswith(".JK") and len(formatted_ticker) == 4:
            formatted_ticker += ".JK"

        stock = yf.Ticker(formatted_ticker)
        data = stock.history(period="1d")
        if not data.empty:
            return float(data["Close"].iloc[-1])
        return None
    except Exception as e:
        logging.error(f"Gagal mengambil data untuk {ticker_symbol}: {e}")
        return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pesan sambutan saat bot dimulai."""
    welcome_text = (
        "🤖 **Bot Pemantau Saham Siap Digunakan**\n\n"
        "Ketik `/cmd` untuk melihat seluruh daftar command yang siap disalin."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan seluruh list command dalam format yang mudah diklik/disalin."""
    commands_text = (
        "📋 **Daftar Command Bot Saham**\n"
        "*(Ketuk command di bawah untuk menyalin)*\n\n"
        "`/ceksaham BUMI`\n"
        "`/pantausaham BUMI 576`\n"
        "`/daftarpantausaham`\n"
        "`/hapuspantausaham 1`\n"
        "`/cmd`"
    )
    await update.message.reply_text(commands_text, parse_mode="Markdown")


async def cek_saham(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fitur untuk mengecek harga saham secara instan."""
    if not context.args:
        await update.message.reply_text("Format salah. Gunakan: `/ceksaham [KODE_SAHAM]`\nContoh: `/ceksaham BUMI`",
                                        parse_mode="Markdown")
        return

    ticker = context.args[0]
    await update.message.reply_text(f"Sedang mengambil data real-time untuk {ticker.upper()}...")

    price = get_realtime_price(ticker)
    if price is not None:
        await update.message.reply_text(f"Harga terkini **{ticker.upper()}**: Rp {price:,.2f}", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"Gagal menemukan data untuk saham {ticker.upper()}. Periksa kembali kode sahamnya.")


async def pantau_saham(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fitur untuk mendaftarkan target harga ke dalam watchlist."""
    if len(context.args) < 2:
        await update.message.reply_text(
            "Format salah. Gunakan: `/pantausaham [KODE] [HARGA]`\nContoh: `/pantausaham BUMI 576`",
            parse_mode="Markdown")
        return

    ticker = context.args[0].upper()
    try:
        target_price = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Harga target harus berupa angka.")
        return

    chat_id = update.effective_chat.id

    if chat_id not in watchlist:
        watchlist[chat_id] = []

    watchlist[chat_id].append({'ticker': ticker, 'target': target_price})
    assigned_id = len(watchlist[chat_id])

    await update.message.reply_text(
        f"✅ Berhasil ditambahkan!\n"
        f"• **ID Pantauan:** `{assigned_id}`\n"
        f"• **Saham:** {ticker}\n"
        f"• **Target Harga:** Rp {target_price:,.2f}",
        parse_mode="Markdown"
    )


async def daftar_pantau_saham(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan daftar saham yang sedang dipantau pengguna beserta ID-nya."""
    chat_id = update.effective_chat.id

    if chat_id not in watchlist or not watchlist[chat_id]:
        await update.message.reply_text("📭 Kamu belum memiliki daftar pantauan saham aktif.")
        return

    text = "📋 **Daftar Pantauan Saham Kamu:**\n\n"
    for index, item in enumerate(watchlist[chat_id], start=1):
        text += f"*{index}.* Saham: **{item['ticker']}** | Target: Rp {item['target']:,.2f}\n"

    text += "\nGunakan `/hapuspantausaham [ID]` untuk menghapus pantauan."
    await update.message.reply_text(text, parse_mode="Markdown")


async def hapus_pantau_saham(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menghapus pantauan saham berdasarkan nomor ID."""
    chat_id = update.effective_chat.id

    if chat_id not in watchlist or not watchlist[chat_id]:
        await update.message.reply_text("📭 Tidak ada data pantauan untuk dihapus.")
        return

    if not context.args:
        await update.message.reply_text(
            "Format salah. Gunakan: `/hapuspantausaham [ID]`\nContoh: `/hapuspantausaham 1`", parse_mode="Markdown")
        return

    try:
        idx_to_delete = int(context.args[0]) - 1
    except ValueError:
        await update.message.reply_text("ID harus berupa angka.")
        return

    if 0 <= idx_to_delete < len(watchlist[chat_id]):
        removed_item = watchlist[chat_id].pop(idx_to_delete)
        await update.message.reply_text(
            f"🗑 Berhasil menghapus pantauan:\n"
            f"Saham **{removed_item['ticker']}** (Target: Rp {removed_item['target']:,.2f})",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ ID pantauan tidak ditemukan. Cek kembali melalui `/daftarpantausaham`.",
                                        parse_mode="Markdown")


async def check_watchlist_job(application):
    """Fungsi latar belakang untuk memeriksa seluruh watchlist pengguna."""
    for chat_id, stocks in list(watchlist.items()):
        for index in range(len(stocks) - 1, -1, -1):
            item = stocks[index]
            ticker = item['ticker']
            target = item['target']

            current_price = get_realtime_price(ticker)
            if current_price is not None:
                if current_price <= target:
                    msg = (
                        f"🚨 **ALERT SAHAM TERPICU!** 🚨\n"
                        f"Saham **{ticker}** telah menyentuh target!\n\n"
                        f"• Harga Sekarang: Rp {current_price:,.2f}\n"
                        f"• Target Anda: Rp {target:,.2f}"
                    )
                    await application.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
                    stocks.pop(index)


def main():
    """Inisialisasi dan menjalankan bot."""
    application = ApplicationBuilder().token(TOKEN).build()

    # Daftarkan Handler Command
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cmd", cmd_list))
    application.add_handler(CommandHandler("ceksaham", cek_saham))
    application.add_handler(CommandHandler("pantausaham", pantau_saham))
    application.add_handler(CommandHandler("daftarpantausaham", daftar_pantau_saham))
    application.add_handler(CommandHandler("hapuspantausaham", hapus_pantau_saham))

    # Konfigurasi Background Scheduler untuk cek harga tiap 5 menit sekali
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: application.job_queue.run_once(lambda ctx: check_watchlist_job(application), 0),
                      'interval', minutes=5)
    scheduler.start()

    print("Bot sedang berjalan...")
    application.run_polling()


if __name__ == "__main__":
    main()
