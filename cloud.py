import os
from google.cloud import pubsub_v1


def notify(message):
    publisher = pubsub_v1.PublisherClient()
    topic_name = 'projects/{project_id}/topics/{topic}'.format(
        project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
        topic=os.getenv('GOOGLE_PUBSUB_TOPIC'),
    )
    future = publisher.publish(topic_name, bytes(message, encoding="utf-8"), spam='eggs')
    future.result()
