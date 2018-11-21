#!/usr/bin/env bash
# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

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
