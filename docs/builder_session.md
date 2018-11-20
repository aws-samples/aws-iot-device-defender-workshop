# Intro

# Goals

1. Create Device Defender Security Profile
1. Create a lambda to automate response to a security profile violation
1. Trigger a Profile violation

# Instructions
_Steps 1-4 are shared with the workshop_
1. Create Cloudformation Stack
This stack will create the following resources in your AWS Account:
   - Cloud9 IDE Instance
   - EC2 Webserver instance
   - SNS Topic for Device Defender Notifications
   - IAM Role to Allow Device Defender to publish events to SNS
   - IAM Role for Lambda Execution
1. Enter Cloud9 IDE Instance
1. Run bootstrap script
1. Run provision thing script
1. Create a quarantine thing group
1. Create Lambda Function
   - Start from the SNS Python Template
   ```python
   from __future__ import print_function

    import json
    import boto3

    def lambda_handler(event, context):
        message = event['Records'][0]['Sns']['Message']
        violation = json.loads(message)
        thing_name = violation["thingName"]
        print("ThingName:" + thing_name)
        client = boto3.client('iot')
        response = client.add_thing_to_thing_group(thingGroupName="Quarantine", thingName=thing_name)
        print(response)
        return message
    ```
1. Setup SNS Subscription to lambda
   - may also want to have it send email
1. Run Agent
   - Let it run for ~5 minutes to publish a report and establish a baseline
1. Run attack script
   - will need to wait for another ~5 minutes for report
   
# Cleanup
1. Cleanup provision-things created IoT Resources
1. Remove Lambda
1. Remove Lamda IAM Role
1. Delete Cloudwatch Log Groups


# Troubleshooting
## Problem: Getting an error in botocore when trying to use the aws cli
```
ImportError: cannot import name AliasedEventEmitter
```
### Solution
```
sudo yum downgrade aws-cli.noarch python27-botocore
```