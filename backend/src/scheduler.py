from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging

logger = logging.getLogger('scheduler')

class TaskScheduler:
    """Manage scheduled tasks using APScheduler"""
    
    def __init__(self, db=None):
        self.scheduler = AsyncIOScheduler()
        self.db = db
    
    async def is_paused(self):
        """Check if system is globally paused"""
        if not self.db:
            return False
        return await self.db.get_system_state('is_paused') == 'true'
    
    def add_researcher_job(self, callback, interval_minutes=15):
        """Schedule researcher bot to run every N minutes"""
        async def job_wrapper():
            if await self.is_paused():
                logger.info("Skipping researcher job (system paused)")
                return
            await callback()

        self.scheduler.add_job(
            job_wrapper,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id='researcher_bot',
            name='Researcher Bot',
            replace_existing=True
        )
        logger.info(f'Added researcher job: every {interval_minutes} minutes')
    
    def add_position_monitor_job(self, callback, interval_seconds=60):
        """Schedule position monitor to run every N seconds"""
        async def job_wrapper():
            if await self.is_paused():
                # We log less frequently for the monitor to avoid spam
                return
            await callback()

        self.scheduler.add_job(
            job_wrapper,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id='position_monitor',
            name='Position Monitor',
            replace_existing=True
        )
        logger.info(f'Added position monitor job: every {interval_seconds} seconds')
    
    def add_daily_summary_job(self, callback, hour=23, minute=55):
        """Schedule daily summary at specific time (UTC)"""
        self.scheduler.add_job(
            callback,
            trigger=CronTrigger(hour=hour, minute=minute),
            id='daily_summary',
            name='Daily Summary',
            replace_existing=True
        )
        logger.info(f'Added daily summary job: {hour:02d}:{minute:02d} UTC')
    
    def add_weekly_analyst_job(self, callback, day_of_week='mon', hour=8, minute=0):
        """Schedule Agent 9 Performance Analyst to run weekly (default: Monday 08:00 UTC)"""
        self.scheduler.add_job(
            callback,
            trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute),
            id='weekly_analyst',
            name='Agent 9 Performance Analyst',
            replace_existing=True
        )
        logger.info(f'Added weekly analyst job: every {day_of_week} at {hour:02d}:{minute:02d} UTC')
        
    def add_custom_job(self, name: str, callback, interval_minutes: int, skip_when_paused: bool = True):
        """Schedule a custom job to run every N minutes.
        
        Args:
            skip_when_paused: If False, the job runs even when system is paused.
                              Set to False for critical jobs like Telegram command polling.
        """
        async def job_wrapper():
            if skip_when_paused and await self.is_paused():
                logger.info(f"Skipping {name} job (system paused)")
                return
            await callback()

        job_id = name.lower().replace(' ', '_')
        self.scheduler.add_job(
            job_wrapper,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            name=name,
            replace_existing=True,
            next_run_time=datetime.utcnow()  # Fire immediately on first run
        )
        logger.info(f'Added custom job {name}: every {interval_minutes} minutes (skip_when_paused={skip_when_paused})')
    
    def add_midnight_reset_job(self, callback):
        """Schedule daily reset at midnight UTC"""
        self.scheduler.add_job(
            callback,
            trigger=CronTrigger(hour=0, minute=0),
            id='midnight_reset',
            name='Midnight Reset',
            replace_existing=True
        )
        logger.info('Added midnight reset job: 00:00 UTC')
    
    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info('Scheduler started')
    
    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info('Scheduler stopped')
    
    def get_jobs(self):
        """Return list of scheduled jobs"""
        return self.scheduler.get_jobs()
    
    def remove_job(self, job_id: str):
        """Remove a scheduled job"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f'Removed job: {job_id}')
        except Exception as e:
            logger.error(f'Error removing job: {e}')
