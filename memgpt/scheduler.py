from apscheduler.schedulers.background import BackgroundScheduler

def get_scheduler():
    global scheduler
    if 'scheduler' not in globals():
        scheduler = BackgroundScheduler()
        scheduler.start()
    return scheduler
