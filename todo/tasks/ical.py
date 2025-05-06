import os
import icalendar
import datetime
import time
from celery import Celery

celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND")
celery.conf.task_default_queue = os.environ.get("CELERY_DEFAULT_QUEUE", "ical")

@celery.task(name="ical")
def create_ical(tasks):
    cal = icalendar.Calendar()
    cal.add("prodid", "-//Taskoverflow Calendar//mxm.dk//")
    cal.add("version", "2.0")

    time.sleep(2)

    for task in tasks:
        event = icalendar.Event()
        event.add("uid", task["id"])
        event.add("summary", task["title"])
        event.add("description", task["description"])
        event.add("dtstart", datetime.datetime.fromisoformat(task["deadline_at"]))
        cal.add_component(event)

    return cal.to_ical().decode("utf-8")

@celery.task(name="ical.test")
def test_task():
    print(">> Test task is running!")
    return "Test successful"
