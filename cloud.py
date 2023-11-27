import os
from google import pubsub_v1
from google.auth import api_key

def pub(message):
    creds = api_key.Credentials(api_key=os.getenv('GOOGLE_API_KEY'))
    publisher = pubsub_v1.PublisherClient(credentials=creds,)
    topic_name = 'projects/{project_id}/topics/{topic}'.format(
        project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
        topic=os.getenv('GOOGLE_PUBSUB_TOPIC'),
    )
    future = publisher.publish(topic_name, bytes(message, encoding="utf-8"), spam='eggs')
    future.result()
