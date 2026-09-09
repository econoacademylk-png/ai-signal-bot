import os
import threading
import app
import bot
import time

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_trading_bot():
    # Small delay to ensure Flask starts first
    time.sleep(2)
    bot.run_bot()

if __name__ == '__main__':
    print("Starting AIBot Backend Server...")
    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    bot_thread = threading.Thread(target=run_trading_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
