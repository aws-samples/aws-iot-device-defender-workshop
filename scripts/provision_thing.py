#!/usr/bin/env python2
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

import boto3
from botocore.exceptions import ClientError
import json
import os
import argparse

THING_NAME = "DefenderWorkshopThing"
POLICY_NAME = "DefenderWorkshopPolicy"
GROUP_NAME = "DefenderWorkshopGroup"

client = boto3.client('iot')


def generate_agent_args_file(agent_args):
    with open("../certificates/AmazonRootCA1.pem", "r") as ca_file:
        agent_args += ["-r", os.path.realpath(ca_file.name)]

    agent_args += ["-f", "json"]

    with open("agent_args.txt", "w") as agent_args_file:
        agent_args_file.writelines('\n'.join(agent_args) + '\n')


def cleanup_things():
    with open("../certificates/certificate_id.txt", "r") as id_file:
        cert_id = id_file.read()

    client.detach_policy(policyName=POLICY_NAME, target=cert_id)
    client.update_certificate(certificateId=cert_id,
                              newStatus="INACTIVE")
    client.delete_certificate(certificateId=cert_id)
    client.delete_thing(THING_NAME)
    client.delete_thing_group(GROUP_NAME)
    client.delete_policy(POLICY_NAME)


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--cleanup", required=False, action="store_true", dest="cleanup",
                        help="Cleanup resources created by previous invocations of this script")

    args = parser.parse_args()

    if args.cleanup:
        cleanup_things()
    else:
        try:
            agent_args = []
            if not client.list_things(attributeName=THING_NAME, attributeValue=THING_NAME)['things']:
                response = client.create_thing(thingName=THING_NAME)
                thingArn = response['thingArn']
                thingId = response['thingId']
                print("Created Thing: " + thingId)
            else:
                print "Thing Already Exists, please choose another name, or delete existing thing"
                exit(1)

            agent_args += ["-id", THING_NAME]

            response = client.create_keys_and_certificate(setAsActive=True)
            certificatePem = response['certificatePem']
            certificateArn = response['certificateArn']
            keyPair = response['keyPair']
            print("Created Certificate  arn:" + certificateArn + "\n id:" + response['certificateId'])

            with open("../certificates/certificate.pem", "w") as certificateFile:
                certificateFile.write(certificatePem)
                agent_args += ["-c", os.path.realpath(certificateFile.name)]

            # Save the certificate id to a file so we can easily cleanup later
            with open("../certificates/certificate_id.txt", "w") as certificateIdFile:
                certificateIdFile.write(response['certificateId'])

            with open("../certificates/private_key.key", "w") as private_key:
                private_key.write(keyPair["PrivateKey"])
                private_key
                agent_args += ["-k", os.path.realpath(private_key.name)]

            response = client.attach_thing_principal(thingName=THING_NAME, principal=certificateArn)
            print("Attached Certificate to Thing: " + THING_NAME)

            with open("iot_policy.json", "r") as policyFile:
                policy = json.load(policyFile)

            policies = client.list_policies()['policies']

            policyArn = ""
            for p in policies:
                if p['policyName'] == POLICY_NAME:
                    policyArn = p['policyArn']
                    policyName = POLICY_NAME
                    print("Using Existing Policy")

            if not policyArn:
                response = client.create_policy(policyName=POLICY_NAME, policyDocument=json.dumps(policy))
                policyArn = response['policyArn']
                print("Created Policy: " + POLICY_NAME)

            response = client.attach_policy(policyName=POLICY_NAME, target=certificateArn)
            print("Attached Policy to Certificate")

            response = client.describe_endpoint(endpointType='iot:Data-ATS')
            agent_args += ["-e", response['endpointAddress']]

            # Create a Thing Group to put our new thing into
            response = client.create_thing_group(
                thingGroupName=GROUP_NAME
            )
            thingGroupArn = response['thingGroupArn']

            # Add our workshop thing to the new group
            response = client.add_thing_to_thing_group(
                thingGroupArn=thingGroupArn,
                thingArn=thingArn
            )

            generate_agent_args_file(agent_args)
        except ClientError as e:
            print e;
