from src.celery_app import celery_app

@celery_app.task(name="tasks.add")
def add(x, y):
    return x + y