from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from heroic_api.tasks import poll_rubin_schedule


def run():
    scheduler = BlockingScheduler()
    scheduler.add_job(
        poll_rubin_schedule.send,
        CronTrigger.from_crontab('*/10 * * * *'),
        max_instances=1,
        replace_existing=True
    )
    scheduler.start()
