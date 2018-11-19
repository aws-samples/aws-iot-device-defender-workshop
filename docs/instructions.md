# Workshop Steps
## Pre-reqs (host laptop)

  - AWS Account
  - git
  - Clone workshop repo from Github
  ```
  git clone https://github.com/aws-samples/aws-iot-device-defender-workshop.git
  ```

## Create your Workshop Cloudformation Stack

We will create an online development environment. This environment will
let us simulate an IoT thing, and a malicious process running on that thing. Because Cloud9 automatically sets up your AWS credentials, it will let us quickly test out different features of Device Defender and run our simulated attack.

This CloudFormation Stack will create:

  - A Cloud9 IDE and associated EC2 instance
  - An EC2 instance to serve as a target for our simulated attack

### Steps

  - From the AWS Console, navigate to [CloudFormation]: https://console.aws.amazon.com/cloudformation/home
  - Click the "Create Stack" button,
  - Choose "Upload a template to S3", select the
    **workshop.yaml** from the cloudformation directory of the workshop github repository you cloned earlier
  - Click "Next"
  - Give your stack a name: "Device Defender Workshop"
  - You can leave the hibernate and instance type fields as they are
  - In Subnet, choose the subnet you'd like to use
      - if you are unsure, choose the first one in the list
  - In KeyName, Select the Keypair you'd like to use for ssh access to your instances
  - Click "Next" on the following screen
  - Check the "I acknowledge that AWS CloudFormation might create IAM resources." box to continue
  - Click the "Create Stack" button at the bottom of the screen
  - Wait for stack to finish, you should see "CREATE COMPLETE" in the status column after a few minutes
      - Tip: *you may need to refresh your screen to see the updated
        status of your stack*

## Login into your C9 Environment

  - Go to C9 in the AWS Console: https://console.aws.amazon.com/cloud9/home
  - Enter the environment "Device Defender Workshop", by clicking the "Open Ide" button

### Install prereqs

In this step, we will run a small shell script that will setup the environment so we can quickly get started learning about Device Defender

- Amazon Certificate Authorities
- Install Boto3 python library for AWS
- Install AWS Iot Device SDK python package
- Install AWS Iot Device Defender Agent SDK Python Package

#### Steps

From a console tab towards the bottom of your Cloud9 Ide, run "bootstrap.sh" script

   ```
   ./scripts/bootstrap.sh
   ```
## Create your AWS IoT Thing

  In this step, we will run a python script that will automate creating an AWS Iot Thing, this will be the thing that we are simulate in our Cloud9 instance:
  - An IoT Thing Group
  - An IoT Thing, registered in IoT Device management, placed in the group we created
  - An IoT Certificate, attached to your Thing
  - An IoT Policy attached to the Certificate
  - An agent_args.txt file to make running the Device Defender Agent easier

### Running the Create_Thing script

```
python scripts/provision_thing.py

```

## Setup an SNS Topic for Device Defender Violation Notifications

Device Defender has the ability to send notification of a Behavior Profile violation via an SNS Topic. For this workshop, we will configure an SNS topic and enable email delivery of the notifications.

### Setting up the SNS Topic

- Navigate to the [SNS Console]: https://console.aws.amazon.com/sns/v2/home
- Click "Create Topic"
- For Topic Name: "DeviceDefenderNotifications"
- For Display Name: "Device Defender Notifications"
- In the Topic Details screen for your newly created topic, click "Create Subscription"
- For Protocol, select "Email"
- For Endpoint enter your email address
- Click "Confirm Subscription" link in the email
  - Note: the sender of the email will be the same as the Display Name you entered for the topic.

## Configure a behavior profile (AWS IoT Console Version)

Now that we have our simulated thing created and we have a development
environment, we are ready to configure a behavior profile in device
defender

- Navigate to the Security Profiles Section of the Device Defender Console
AWS Iot -> Defend -> Detect -> Security Profiles
https://console.aws.amazon.com/iot/home#/dd/securityProfilesHub

- Click the "Create" button
- Configure parameters
- Name: "NormalNetworkTraffic"
- Under Behaviors
  - **Name:** "Packets Out"
  - **Metric:** "Packets Out"
  - **Operator:** "Less Than"
  - **Value:** "100"
  - **Duration:** "5 minutes"
- Attach profile to group
- *script creates a specific group name*
      - Setup alerting SNS
      - Select SNS Topic "DefenderWorkshopNotifications"
      - Select Role "DefenderWorkshopNotificationRole" 
  - Lambda for moving thing to "quaratine" thing group??

## Start the Agent

The next component of Device Defender we are going to look at is the
Device Agent. The detect function of DD, can utilize both cloud-side
metrics and device-side metrics. For device-side metrics, we need
something that runs on teh device and collects metrics and sends them to
DD. For this we provides reference implementations of agents that you
can use as the basis for your own device-defender integration.

The reference agent we will be using today is the python agent. It's
operation is fairly simple: periodically it wakes up, takes a sample of
some basic system metrics, compiles them into a metrics report and
publishes them to a reserved Device Defender MQTT Topic. From there, all
processing is done automatically in the cloud by Device Defender.

- Get your custom service endpoint from the IoT Console
  - IoT Console -> Settings
  - Put your endpoint in scripts/agent\_args.txt , replacing the "YOUR_ENDPOINT_HERE" text with your endpoint location
  Run the agent
  ```
  cd scripts
  python usr/local/lib/python2.7/site-packages/AWSIoTDeviceDefenderAgentSDK/agent.py @agent_args.txt
  ```
## Start the attacker

- Get your Target server URL from the cloudformation outputs
- In a second console tab (leave the agent running), run "ab" tool, which will generate load from your "device" to the target server

```
#Note: the trailing space is necessary here:
ab -n 10000 http://YOUR_TARGET_INSTANCE_URL/
```

## View Violations
### AWS IoT Console
- Iot -> Defend -> Detect -> Violations
- View the "Now" tab to see current state
- View the "History" tab to see how the device has changed over time

## Check violation email
- You should see an email from SNS indicating the violation
## Confirm Violation has cleared
- After approximateley 10 minutes after you stop running AB, your device should no longer be in violation. _Note_ You can always check your violations history tab to see how the security posture of your devices changed over time. 

# Cleanup
 -  Delete your cloudformation stack
 -  Delete all resources associated with DefenderWorkshop in your IoT Account
