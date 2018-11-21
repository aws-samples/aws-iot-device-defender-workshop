# Goals

1. Create a Device Defender Security Profile
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

## Create a quarantine thing group
1. Navigate to the [IoT Console](https://console.aws.amazon.com/iot/home)
1. From the left hand menu select  "Manage", and then "Things Groups"
1. Click the "Create" button in the upper right corner
1. Click the "Create Thing Group" button
1. Enter "Quarantine" in the "Name" field
1. Click "Create Thing Group"

## Create Lambda Function
In this section, we will create a Lambda function that will fire in response to 
Device Defender Violation SNS events. It will extract the Thing Name of the device
that is in violation of the Security Profile and move it to our "Quarantine" thing group,
so we can easily find it for further investigation and remediation.

1. Navigate to the [Lambda Console](https://console.aws.amazon.com/lambda/home)
1. Click "Functions" on the left hand menu
1. Click the "Create function" button
1. Select "Blueprints"
1. In search box under Blueprints, search for "sns"
1. Select the "sns-message-python" blueprint and click "Configure"
1. Give your function the name "DeviceDefenderViolation"
1. Select "Choose an Existing Role" in the "Role" drop-down
1. Choose the role "DeviceDefenderBuilderLambda" in the "Existing Role" drop-down
1. Select the SNS Topic that has "DeviceDefenderNotifications" as part of the name
1. Check the "Enable Trigger" checkbox
1. Click the "Create Function" button (_we'll get to edit the code in the next step_)
1. In the Lambda detail page, edit the function code so it looks like the following:
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
1. Click the save button

## Run Agent
1. Return to your Cloud9 environment
1. From the console, run your Device Defender Agent
 ```bash
  cd scripts
  python /usr/local/lib/python2.7/site-packages/AWSIoTDeviceDefenderAgentSDK/agent.py @agent_args.txt
  ```
1. Wait for about 5 minutes, until your agent has published two metrics reports
You should see two lines similar to this:
```bash
Received a new message: 
{"thingName":"DefenderWorkshopThing","reportId":1542697506,"status":"ACCEPTED","timestamp":1542697506269}
```
## Start the Attacker
1. Get your Target server URL from the CloudFormation outputs from the stack you created earlier
1. In a second console tab (leave the agent running), run "ab" tool, which will generate HTTP traffic from your "device" to the target server
   ```bash
      #Note: the trailing space is necessary here:
      ab -n 10000 http://YOUR_TARGET_INSTANCE_URL/
   ```   
1. Wait approximately 5 minutes for another metrics report to be published

## Check your Quarantine thing group
1. Navigate to the [IoT Console](https://console.aws.amazon.com/iot/home)
1. From the left hand menu select  "Manage", and then "Things Groups"
1. Click on the "Quarantine" group
1. In the Group Detail screen, click "Things" in the left hand menu
1. Verify you now see a thing called "DefenderWorkshopThing" in the thing group.

# Cleanup
 1. Delete your IoT Resources created with the provision_thing script
    ```bash
       cd scripts
       ./provision_thing.py --cleanup
    ```
 1. Delete your CloudFormation stack
 1. Delete all other AWS resources associated with DefenderWorkshop
    - Quarantine Thing Group
    - Device Defender Behavior Profile


# Troubleshooting
## Problem: Getting an error in botocore when trying to use the aws cli
```
ImportError: cannot import name AliasedEventEmitter
```
### Solution
```
sudo yum downgrade aws-cli.noarch python27-botocore
```
