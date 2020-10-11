"""
Lambda handler module invoked during stack create/update/delete.
Adds monitoring and alarms for new/updated resouces
"""
from aws_lambda_powertools import Logger
import boto3

from dashboard import update_dashboard

LOG = Logger()

cw_client = boto3.client('cloudwatch')


@LOG.inject_lambda_context
def watch_existing(event, _):
    """ Handle create/update/delete of CloudFormation stacks """
    # services = event.get('WatchServices'
    # tag_filter = event['TagFilter']

    update_dashboard()
    return {}