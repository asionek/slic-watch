import boto3
import os

from aws_lambda_powertools import Logger
from concurrent import futures
from lambdas import get_applicable_lambdas

SNS_ALARMS_TOPIC = os.getenv('SNS_ALARMS_TOPIC')
MAX_CONCURRENCY = 3
LOG = Logger()

cloudwatch_client = boto3.client('cloudwatch')


def create_lambda_errors_alarm(func_name, threshold, period):
    ''' Create an alarm for Lambda errors '''
    alarm_name = f'LambdaError_{func_name}'
    LOG.info(f'Creating alarm {alarm_name}')
    return cloudwatch_client.put_metric_alarm(
        AlarmName=alarm_name,
        Period=period,
        EvaluationPeriods=1,
        MetricName='Errors',
        Namespace='AWS/Lambda',
        Statistic='Sum',
        ComparisonOperator='GreaterThanThreshold',
        Threshold=threshold,
        ActionsEnabled=True,
        AlarmDescription=f'Alarm for lambda {func_name} errors',
        Dimensions=[{'Name': 'FunctionName', 'Value': func_name}],
        AlarmActions=[SNS_ALARMS_TOPIC]
    )


def create_lambda_throttles_alarm(func_name, threshold, period):
    ''' Create an alarm on the number of throttles as a percentage
        of invocations for a given period

        :func_name The Lambda function name
        :threshold The minimum percentage of throttles to invocations to raise the alarm
        :period The period for evaluation in seconds '''
    alarm_name = f'LambdaThrottles_{func_name}'
    LOG.info(f'Creating alarm {alarm_name}')
    return cloudwatch_client.put_metric_alarm(
        AlarmName=alarm_name,
        EvaluationPeriods=1,
        DatapointsToAlarm=1,
        Metrics=[
            {
                'Id': 'throttles_pc',
                'Expression': '(throttles / invocations) * 100',
                'Label': '% Throttles',
                'ReturnData': True
            },
            {
                'Id': 'throttles',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/Lambda',
                        'MetricName': 'Throttles',
                        'Dimensions': [{'Name': 'FunctionName', 'Value': func_name}]
                    },
                    'Period': period,
                    'Stat': 'Sum'
                },
                'ReturnData': False
            },
            {
                'Id': 'invocations',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/Lambda',
                        'MetricName': 'Invocations',
                        'Dimensions': [{'Name': 'FunctionName', 'Value': func_name}]
                    },
                    'Period': period,
                    'Stat': 'Sum'
                },
                'ReturnData': False
            }
        ],
        ComparisonOperator='GreaterThanThreshold',
        Threshold=threshold,
        ActionsEnabled=True,
        AlarmDescription=f'Alarm for Lambda {func_name} throttles/invocations',
        AlarmActions=[SNS_ALARMS_TOPIC]
    )


def create_lambda_alarms(func_name, errors_threshold, errors_period, throttles_threshold):
    create_lambda_errors_alarm(func_name, errors_threshold, errors_period)
    create_lambda_throttles_alarm(
        func_name, throttles_threshold, errors_period)


def update_alarms(errors_threshold=1.0, errors_period=60, throttles_threshold=1.0):
    lambda_functions = get_applicable_lambdas()
    LOG.info(f'Creating alarms for {lambda_functions}')

    with futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as executor:
        wait_for = [
            executor.submit(create_lambda_alarms,
                            func_name,
                            errors_threshold,
                            errors_period,
                            throttles_threshold)
            for func_name in lambda_functions.keys()
        ]

        for future in futures.as_completed(wait_for):
            LOG.info(future.result())


def get_existing_alarm(func_name):
    alarm_name = f'LambdaError_{func_name}'
    alarms = cloudwatch_client.describe_alarms(AlarmNames=[alarm_name])

    existing_alarm = next(
        (_ for _ in alarms['MetricAlarms'] if _['AlarmName'] == alarm_name),
        None
    )

    return existing_alarm


def delete_alarms(func_name):
    existing_alarm = get_existing_alarm(func_name)

    if existing_alarm:
        response = cloudwatch_client.delete_alarms(
            AlarmNames=[existing_alarm['AlarmName']]
        )

        LOG.info(response)
    else:
        LOG.info(f'No alarms found for function {func_name}')