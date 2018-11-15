#!/usr/bin/env bash
# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   A copy of the License is located at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   or in the "license" file accompanying this file. This file is distributed
#   on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
#   express or implied. See the License for the specific language governing
#   permissions and limitations under the License.

# Install Python Dependencies
# Install Boto3
sudo pip install boto3

#Install Device Defender Sample Agent, it'll pull down the IoT SDK as well
sudo pip install AWSIoTDeviceDefenderAgentSDK

#Get the root ca
wget -P ../certificates https://www.amazontrust.com/repository/AmazonRootCA1.pem
wget -P ../certificates https://www.amazontrust.com/repository/AmazonRootCA2.pem
wget -P ../certificates https://www.amazontrust.com/repository/AmazonRootCA3.pem
wget -P ../certificates https://www.amazontrust.com/repository/AmazonRootCA4.pem
wget -P ../certificates https://www.symantec.com/content/en/us/enterprise/verisign/roots/VeriSign-Class%203-Public-Primary-Certification-Authority-G5.pem
