# Workshop Steps
## Prerequisites

  - AWS Account
    - Have a [Default VPC](https://docs.aws.amazon.com/vpc/latest/userguide/what-is-amazon-vpc.html) configured 
  - [git](https://git-scm.com/downloads) installed on your development machine _(for cloning the workshop repository)_
  - Clone workshop repo from Github
    ```bash
    git clone https://github.com/aws-samples/aws-iot-device-defender-workshop.git
    ```

## Create your Workshop Cloudformation Stack

We will create an online development environment using [AWS Cloud9](https://console.aws.amazon.com/cloud9/home). This environment will
let us simulate an IoT thing, and a malicious process running on that thing. Because Cloud9 automatically sets up your AWS credentials, it will let us quickly test out different features of Device Defender and run our simulated attack.

This CloudFormation Stack will create:

  - A Cloud9 IDE and associated EC2 instance (this will stand in for an IoT Thing)
  - An EC2 instance to serve as a target for our simulated attack

### Steps

  1. From the AWS Console, navigate to [CloudFormation](https://console.aws.amazon.com/cloudformation/home)
  1. Click the "Create Stack" button,
  1. Choose "Upload a template file", and select the
    **workshop.yaml** from the _cloudformation_ directory of the workshop GitHub repository you cloned earlier
  1. Click "Next"
  1. Give your stack a name: "DeviceDefenderWorkshop"
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
  1. Enter the environment "DeviceDefenderWorkshop", by clicking the "Open IDE" button

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

  In this step, we will run a Python script that will automate creating an AWS IoT Thing, this will be the thing that we simulate in our Cloud9 instance:
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

## Setup an SNS Topic for Device Defender Violation Notifications (SNS Console)

Device Defender has the ability to send notification of a Behavior Profile violation via an SNS Topic. 
For this workshop, we will configure an SNS topic and enable email delivery of the notifications.


### Setting up the SNS Topic

1. Navigate to the [SNS Console](https://console.aws.amazon.com/sns/v2/home)
1. Click "Create Topic"
1. For Topic Name: "DeviceDefenderNotifications"
1. For Display Name: "DvcDefendr"
1. In the Topic Details screen for your newly created topic, click "Create Subscription"
1. For Protocol, select "Email"
1. For Endpoint enter your email address
1. Check your email, after a few moments, you should receive a confirmation email
1. Click "Confirm Subscription" link in the email
  - _Note_: the sender of the email will be the same as the Display Name you entered for the topic.

### Create a Target Role for Device Defender SNS Notifications

For this step, we will re-use a policy from AWS IoT Rules Engine, as it has the proper SNS policy in place.

1. Navigate to the [IAM Console](https://console.aws.amazon.com/iam/home)
1. Select Roles from the left hand menu
1. Click "Create Role"
1. In the Select type of trusted entity section, choose "AWS Service"
1. Select "IoT" as the service that will use this role
1. When you select "IoT", a section will appear entitled "Select your use case"
1. Select "IoT"
1. Click "Next:Permissions"
1. Next you will shown a summary of attached policies, you don't need to do anything on this screen
1. Click "Next: Tags"
1. Click "Next: Review"
1. On the Create Role screen enter "DeviceDefenderWorkshopNotification" for the Role Name
1. Click "Create Role"

## Configure a behavior profile (IoT Console)

Now that we have our simulated thing created and we have a development
environment, we are ready to configure a behavior profile in device
defender

1. Navigate to the [Security Profiles Section](https://console.aws.amazon.com/iot/home#/dd/securityProfilesHub) of the Device Defender Console
AWS IoT -> Defend -> Detect -> Security Profiles
1. Click the "Create" button
    - _Note_: If you have no Security Profiles in your account, you will see a "Create your first security profile" button instead
1. Configure parameters
1. Name: "NormalNetworkTraffic"
1. Under Behaviors
  <br/>**Name:** "Packets Out"
  <br/>**Metric:** "Packets Out"
  <br/>**Operator:** "Less Than"
  <br/>**Value:** "10000"
  <br/>**Duration:** "5 minutes"
1. On the Alert Targets Page
   <br/>**SNS Topic:** "DefenderWorkshopNotifications"
   <br/>**Role:** "DeviceDefenderWorkshopNotification"
1. Click Next 
1. Attach profile to group "DefenderWorkshopGroup"
1. Click Next
1. Click Save

## Start the Agent (Cloud9)

The next component of Device Defender we are going to look at is the
Device Agent. The detect function of DD, can utilize both cloud-side
metrics and device-side metrics. For device-side metrics, we need
something that runs on the device and collects metrics and sends them to
Device Defender. For this we provide reference implementations of agents that you
can use as the basis for your own device-defender integration.

The reference agent we will be using today is the Python agent. It's
operation is fairly simple: periodically it wakes up, takes a sample of
some basic system metrics, compiles them into a metrics report and
publishes them to a reserved Device Defender MQTT Topic. From there, all
processing is done automatically in the cloud by Device Defender.

Run the agent from a console tab:
  ```bash
  cd scripts
  python /usr/local/lib/python2.7/site-packages/AWSIoTDeviceDefenderAgentSDK/agent.py @agent_args.txt
  ```
After a few minutes, you should see a message similar to the following:
```
Received a new message: 
{"thingName":"DefenderWorkshopThing","reportId":1542697506,"status":"ACCEPTED","timestamp":1542697506269}

```
This is an MQTT message sent from Device Defender to the agent, acknowledging acceptance
of a metrics report.
  
## Start the attacker

1. Get your Target server URL from the CloudFormation outputs from the stack you created earlier
1. In a second console tab (leave the agent running), run "ab" tool, which will generate HTTP traffic from your "device" to the target server
   ```bash
      #Note: the trailing space is necessary here:
      ab -n 10000 http://YOUR_TARGET_INSTANCE_URL/
   ```

## View Violations

### AWS IoT Console

1. IoT -> Defend -> Detect -> Violations
1. View the "Now" tab to see current state
1. View the "History" tab to see how the device has changed over time

## Check violation email

You should see an email from SNS indicating the violation the contents will look something like this:

```
{"violationEventTime":1542682416515,"thingName":"DefenderWorkshopThing","behavior":{"criteria":{"value":{"count":100},"durationSeconds":300,"comparisonOperator":"less-than"},"name":"PacketsOut","metric":"aws:all-packets-out"},"violationEventType":"alarm-cleared","metricValue":{"count":29},"violationId":"76ef8d1dc35ed4eb802ff44568f91097","securityProfileName":"NormalHTTPTraffic"}

--
If you wish to stop receiving notifications from this topic, please click or visit the link below to unsubscribe:
https://sns.us-east-1.amazonaws.com/unsubscribe.html?SubscriptionArn=arn:aws:sns:us-east-1:890450227363:DefenderNotifications:792ddc79-88e4-49c4-ac4a-2126efea0269&Endpoint=damiller@amazon.com

Please do not reply directly to this email. If you have any questions or comments regarding this email, please contact us at https://aws.amazon.com/support
```

## Confirm Violation has cleared

After approximately 10 minutes after you stop running AB, your device should no longer be in violation.
_Note_ You can always check your violations history tab to see how the security posture of your devices changed over time. 

# Cleanup
 1. Delete your IoT Resources created with the provision_thing script
    ```bash
       cd scripts
       ./provision_thing.py --cleanup
    ```
 1. Delete your CloudFormation stack
 1. Delete all other AWS resources associated with DefenderWorkshop
    - SNS Topic
    - SNS Subscription
    - IAM Role
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
## Problem: Cannot access URL for my target server
### Solution
Make sure you append a trailing slash on the url: http://my.ec2.ip.aeces/