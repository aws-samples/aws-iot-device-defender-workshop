# Goals

1. Create a Device Defender Security Profile
1. Create a lambda to automate response to a security profile violation
1. Trigger a Profile violation

## Prerequisites

  - AWS Account
  - Have a [Default VPC](https://docs.aws.amazon.com/vpc/latest/userguide/what-is-amazon-vpc.html) configured 
  - [git](https://git-scm.com/downloads) installed on your development machine _(for cloning the workshop repository)_
  - Create an [EC2 SSH Keypair](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html#having-ec2-create-your-key-pair)
  - Clone workshop repo from Github
    ```bash
    git clone https://github.com/aws-samples/aws-iot-device-defender-workshop.git
    ```

### Steps

  1. From the [AWS Management Console](https://console.aws.amazon.com/console), navigate to [CloudFormation](https://console.aws.amazon.com/cloudformation/home)
  1. Click the "Create Stack" button,
  1. Choose "Upload a template file", and select the
    **builder.yaml** from the _cloudformation_ directory of the workshop GitHub repository you cloned earlier
  1. Click "Next"
  1. Give your stack a name: "DeviceDefenderBuilderSession"
  1. You can leave the AutoHibernateTimeout and InstanceType fields as they are
  1. In SubnetIdentifier, choose the subnet you'd like to use
      - if you are unsure, choose the first one in the list
  1. In KeyName, Select the key pair you'd like to use for ssh access to your instances
  1. Click "Next" on the following screen
  1. Check the "I acknowledge that AWS CloudFormation might create IAM resources." box to continue
  1. Click the "Create Stack" button at the bottom of the screen
  1. Wait for stack to finish, you should see "CREATE COMPLETE" in the status column after a few minutes
      - Tip: *you may need to refresh your screen to see the updated
        status of your stack*

## Login into your Cloud9 Environment

  1. Go to the [Cloud9 Console](https://console.aws.amazon.com/cloud9/home)
  1. Enter the environment "DeviceDeviceDefenderBuilderSession", by clicking the "Open IDE" button

### Install prerequisites

In this step, we will run a small shell script that will setup the environment so we can quickly get started learning about Device Defender

- Download Amazon CA certificates
- Install Boto3 python library for AWS
- Install AWS IoT Device SDK python package
- Install AWS IoT Device Defender Agent SDK Python Package

#### Steps

From a console tab towards the bottom of your Cloud9 IDE, run "bootstrap.sh" script
   ```bash
   cd scripts
   ./bootstrap.sh
   ```
## Create your AWS IoT Thing

  In this step, we will run a Python script that will automate creating an AWS IoT Thing, this will be the "Thing" that we simulate in our Cloud9 instance.  This script will create the following:

  - An IoT Thing Group
  - An IoT Thing, registered in IoT Device management, placed in the group we created
  - An IoT Certificate, attached to your Thing
  - An IoT Policy attached to the Certificate
  - An agent_args.txt file to make running the Device Defender Agent easier

### Running the Thing Provisioning script
While in the _scripts_ directory, run the following
  ```bash
  ./provision_thing.py
  ```

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
