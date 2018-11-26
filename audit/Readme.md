# Goals
1. Configure account to turn ON audit checks
2. Schedule a Daily Audit task
3. Execute an OnDemand Audit
4. Automate response to Audit alert using Lambda

# Instructions
## Prerequisites
- AWS Account

## Install dependencies
- sudo yum install git
  - To download script which sets up the account with resources to Audit.
- sudo pip install boto3
- sudo pip install cryptography
- If you are unable to install the above on your host, see instructions below to [create a new EC2 instance](#create-new-ec2-instance)

## Configure AWS credentials
- If you are using an EC2 instance created above, then you can skip this step.
- You would need access to credentials that have permissions for:
  - Creating a S3 bucket
  - Writing into the S3 bucket
  - AWSIoTFullAccess
- If you don't have such credentials, follow the steps below to [create a new User](#iam-user-with-permissions-for-creating-audit-resource)
- If you have access to such credentials, set the following env variables:
  - AWS_ACCESS_KEY_ID
  - AWS_SECRET_ACCESS_KEY
  - AWS_SESSION_TOKEN (only applicable if you are using temporary credentials)

## Create IoT resources to audit
- Download the git repository:
  ```bash
    git clone https://github.com/aws-samples/aws-iot-device-defender-audit.git
  ```
- Execute the setup script:
  ```bash
    python scripts/iot-device-defender-audit-resources-setup.py --region <region>
  ```
- You can execute the above script multiple times to create more test resources in your account by setting the --skip-cleanup flag:
  ```bash
    python scripts/iot-resources-setup.py --region <region> --skip-cleanup
  ```

## Create IAM Role for DeviceDefender-Audit to use
1. Navigate to [IAM Roles Console](https://console.aws.amazon.com/iam/home#/roles)
2. Click **Create Role**
3. Select **IoT** in services and **IoT - Device Defender Audit** in use-case
4. Add **DeviceDefender-Audit-Demo-Role** as RoleName and click **Create role**
5. Now click on the new role that was created and click on **Add inline policies**
6. In the **Visual editor** choose the following:
  - Service: **SNS**
  - Access Level: **Write: [Publish]**
  - Resources: **Add ARN: Region=ANY, Account=ANY, Topic name=DeviceDefender-Audit-Demo**
7. Click **Review Policy** and then add PolicyName and click **Create policy**

## Configure account to turn ON audit checks
1. Navigate to [IoT Device Defender Console](https://console.aws.amazon.com/iot/home#/dd/auditIntro)
2. Click on "Get started with an audit"
3. In the "Select checks" page, unselect the following checks:
  - Authenticated Cognito role overly permissive
  - Device certificate shared
  - Unauthenticated Cognito role overly permissive
  - Device identity shared
  - **Note: these checks should be turned ON for production systems. For the purpose of demo, these checks are not turned ON only to save time**
4. Enable SNS:
  - Create a new Topic (Name: DeviceDefender-Audit-Demo)
  - In the Role dropdown, select **DeviceDefender-Audit-Demo-Role**
5. Click **Enable Audit**
6. By default, a Daily Scheduled Audit is created on your behalf. Feel free to modify that schedule or add additional schedules

## Execute an OnDemand Audit
1. Navigate to [IoT Device Defender Console](https://console.aws.amazon.com/iot/home#/dd/auditIntro)
2. Click on **Schedules**
3. Click on **Create** button on the top-right of the screen
4. Leave all the default settings in place and click **Create** to execute the OnDemand Audit
 
## Perform Mitigation actions using Lambda Function
In this section, we will create a Lambda function that will fire in response to 
Device Defender Audit SNS alerts. In this particular demo, the lambda function will revoke from AWS IoT any
device certificates that is still active in the account, but has been revoked by certificate's issuer.

### Create IAM Role for Audit Mitigation Lambda
1. Navigate to [IAM Roles Console](https://console.aws.amazon.com/iam/home#/roles)
2. Click **Create role** and choose **Lambda** as the service and then click **Next: Permissions**
3. Search for **AWSIoTFullAccess** and select the checkbox next to the search result
4. Next, search for **AWSLambdaBasicExecutionRole** and select the checkbox next to the search result
5. Click **Next: Tags** and finally add role name as **DeviceDefender-Audit-Demo-Mitigation-Lambda** and click **Create role**

### Create Lambda function
1. Navigate to the [Lambda Console](https://console.aws.amazon.com/lambda/home)
1. Click **Functions** on the left hand menu
2. Click the **Create function** button
3. Select **Blueprints**
4. In search box under Blueprints, search for **sns**
5. Select the **sns-message-python** blueprint and click **Configure**
6. Give your function the name **DeviceDefender-Audit-Demo-Mitigation**
7. Select **Choose an existing role** in the **Role** drop-down
8. Choose the role **DeviceDefender-Audit-Demo-Mitigation-Lambda** in the "Existing Role" drop-down
9. Select the SNS Topic that has **DeviceDefender-Audit-Demo** as part of the name
10. Check the "Enable Trigger" checkbox
11. Click the "Create Function" button (_we'll get to edit the code in the next step_)
12. In the Lambda detail page, edit the function code so it looks like the following:

  ```
  from __future__ import print_function

  import json
  import boto3

  iot_client = boto3.client('iot')
  revokedDeviceCertsCheckName = 'REVOKED_DEVICE_CERTIFICATE_STILL_ACTIVE_CHECK'

  # This function will check if there are any Audit findings that have detected
  # any Revoked certificates are being marked as Active in IoT. It then goes ahead
  # and marks those certificates as 'REVOKED' with IoT to prevent any Device from
  # using that certificate to connect any more to AWS IoT.
  def lambda_handler(event, context):
      # Extract Audit notification
      notification = json.loads(event['Records'][0]['Sns']['Message'])

      # Proceed with mitigations only if there are nonCompliantChecks
      num_non_compliant_checks = notification['nonCompliantChecksCount']
      if num_non_compliant_checks > 0:
          audit_checks = notification['auditDetails']

      # Iterate through the auditCheckDetails to see if revoked device certs
      # check has found any non-compliant resources
      for audit_check in audit_checks:
          if (audit_check['checkName'] == revokedDeviceCertsCheckName and
                  audit_check['nonCompliantResourcesCount'] > 0):

              # Iterate through the Audit Findings to populate the list of revoked
              # certificates that are still active.
              certs_to_deactivate = []

              response = \
                  iot_client.list_audit_findings(
                      checkName = revokedDeviceCertsCheckName,
                      taskId = notification['taskId'])
        
              while True:
                  for finding in response['findings']:
                      resource = finding['nonCompliantResource']['resourceIdentifier']
                      certificate_id = resource['deviceCertificateId']
                      certs_to_deactivate.append(certificate_id)

                  if 'NextToken' in response:
                      next_token = response['nextToken']
                  else:
                      break

                  response = \
                      iot_client.list_audit_findings(
                          checkName = revokedDeviceCertsCheckName,
                          nextToken = next_token,
                          taskId = notification['taskId'])

              for certificate_id in certs_to_deactivate:
                  iot_client.update_certificate(
                      certificateId = certificate_id,
                      newStatus = 'REVOKED')
                  print("Deactivated device certificate: " + str(certificate_id))
    ```
13. Click the save button

## Execute an OnDemand Audit
1. Navigate to [IoT Device Defender Console](https://console.aws.amazon.com/iot/home#/dd/auditIntro)
2. Click on **Schedules**
3. Click on **Create** button on the top-right of the screen
4. Leave all the default settings in place and click **Create** to execute the OnDemand Audit

## Verify mitigation actions
1. Execute an OnDemand Audit [following the above steps](#execute-an-ondemand-audit)
2. Navigate to the [Audit Results Console](https://console.aws.amazon.com/iot/home#/dd/auditResultsHub)
3. Click on the latest **On-demand** audit that as executed above
4. Click on the **Non-compliant checks** and then click on **Revoked device certificate still active** check details
5. Click on one of the **Certificate ID** which was flagged as being active despited being marked as revoked by its CA
6. On the Certificate details page verify that the certificate status now shows up as **REVOKED**
7. You can further go into CloudWatch Logs console to see the Lambda logs to verify execution and actions performed.

## Appendix
### Create Policy for IoT resources creation script
1. Navigate to [IAM Policies Console](https://console.aws.amazon.com/iam/home#/policies)
2. Click **Create policy**
3. Select **JSON** tab and paste the following:
   ```json
   {
      "Version": "2012-10-17",
      "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:PutObjectVersionAcl",
                "s3:CreateBucket",
                "s3:PutObjectAcl",
                "iot:AttachPolicy",
                "iot:DeletePolicy",
                "iot:DeleteCertificate",
                "iot:DetachPolicy",
                "iot:UpdateCACertificate",
                "iot:UpdateCertificate",
                "iot:DeleteCACertificate",
                "iot:SetV2LoggingOptions",
                "iot:ListTargetsForPolicy"
            ],
            "Resource": [
                "arn:aws:s3:::device-defender-audit-demo-*",
                "arn:aws:s3:::device-defender-audit-demo-*/*",
                "arn:aws:iot:::*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "iot:CreatePolicy",
                "iot:GetRegistrationCode",
                "iot:GetV2LoggingOptions",
                "iot:RegisterCertificate",
                "iot:RegisterCACertificate"
            ],
            "Resource": "*"
        }
    ]
  }
   ```
4. Click **Review policy** and add **DeviceDefender-Audit-Demo-Resource-Creation-Policy** as the policy name
5. Finally, click **Create policy** to create this policy

### IAM User with permissions for creating audit resources
1. First, create the "DeviceDefender-Audit-Demo-Resource-Creation-Policy" as described in the [above section for creating Policy](#create-policy-for-iot-resources-creation-script)
2. Navigate to [IAM Users Console](https://console.aws.amazon.com/iam/home#/users)
2. Click **Add User** and put **DeviceDefender-Audit-Demo-User** as the name
3. Select **Programmatic access** and click **Permissions**
4. Click on **Attach existing policies directly**
5. Search for **DeviceDefender-Audit-Demo-Resource-Creation-Policy** and select the checkbox next to the search result
6. Click next and finally **Create user**
7. Download the credentials and store it securely for using it in this demo. Make sure to delete those credentials once testing is complete. You can always create new Access keys if needed.

### Create new EC2 instance
1. First, create the "DeviceDefender-Audit-Demo-Resource-Creation-Policy" as described in the [above section for creating Policy](#create-policy-for-iot-resources-creation-script)
2. Next, navigate to [IAM Roles Console](https://console.aws.amazon.com/iam/home#/roles)
3. Click **Create role** and choose **EC2** as the service and then click **Next: Permissions**
4. Search for **DeviceDefender-Audit-Demo-Resource-Creation-Policy** and select the checkbox next to the search result
5. Add **DeviceDefender-Audit-Demo-Instance-Role** as the Role name and click **Create role**
6. Navigate to [EC2 Console](https://console.aws.amazon.com/ec2/v2/home#Instances)
7. Click **Launch Instance**
8. Search for the ami listed below corresponding to the region and select the first result from the **Community AMIs** list:
   ```
    us-east-1:      ami-0ff8a91507f77f867
    us-west-2:      ami-a0cfeed8
    eu-west-1:      ami-047bb4163c506cd98
    eu-west-2:      ami-f976839e
    eu-central-1:   ami-0233214e13e500f77
    ap-northeast-1: ami-06cd52961ce9f0d85
    ap-northeast-2: ami-0a10b2721688ce9d2
    ap-southeast-1: ami-08569b978cc4dfa10
    ap-southeast-2: ami-09b42976632b27e9b
    us-east-2:      ami-0b59bfac6be064b78
   ```
9. Click on **Configure Instance Details**
10. Select **DeviceDefender-Audit-Demo-Instance-Role** from the dropdown for IAM role
11. Click **Review and Launch** and finally **Launch**
12. If you don't have an existing KeyPair select **Create a new key pair** from the dropdown
   - If you create a new key-pair, give it an appropriate name and **Download** the keypair securely to be able to access the host
13. Finally click **Launch instances**
14. Once the instance is up and running, use the following commands to ssh on the host:
   ```
   chmod 400 <keypair .pem file>
   ssh -i <key-pair .pem file> ec2-user@<ec2-instance dns name or public IP>
   ```

# Troubleshooting
## Problem: Getting an error in botocore when trying to use the aws cli
```
ImportError: cannot import name AliasedEventEmitter
```
### Solution
```
sudo yum downgrade aws-cli.noarch python27-botocore
```