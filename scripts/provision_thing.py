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

IOT_POLICY_FILE = "iot_policy.json"

AMAZON_ROOT_CA__FILE = "../certificates/AmazonRootCA1.pem"
PRIVATE_KEY_FILE = "../certificates/private_key.key"
CERTIFICATE_PEM_FILE = "../certificates/certificate.pem"
CERTIFICATE_ID_FILE = "../certificates/certificate_id.txt"

THING_NAME = "DefenderWorkshopThing"
POLICY_NAME = "DefenderWorkshopPolicy"
GROUP_NAME = "DefenderWorkshopGroup"

client = boto3.client('iot')


def generate_agent_args_file(agent_args_map):
    with open(AMAZON_ROOT_CA__FILE, "r") as ca_file:
        agent_args_map += ["-r", os.path.realpath(ca_file.name)]

    agent_args_map += ["-f", "json"]

    with open("agent_args.txt", "w") as agent_args_file:
        agent_args_file.writelines('\n'.join(agent_args_map) + '\n')


def cleanup_things():
    with open(CERTIFICATE_ID_FILE, "r") as id_file:
        cert_id = id_file.read()
        descr_response = client.describe_certificate(certificateId=cert_id)
        cert_arn = descr_response['certificateDescription']['certificateArn']

    if cert_arn and cert_id:
        print("Detaching Policy")
        client.detach_policy(policyName=POLICY_NAME, target=cert_arn)
        print("Deactivating Certificate")
        client.update_certificate(certificateId=cert_id,
                                  newStatus="INACTIVE")
        print("Detaching Cert from Thing")
        client.detach_thing_principal(thingName=THING_NAME, principal=cert_arn)
        print("Deleting Certificate")
        client.delete_certificate(certificateId=cert_id)
        print("Removing Thing from Thing Group")
        client.remove_thing_from_thing_group(thingGroupName=GROUP_NAME, thingName=THING_NAME)
        print("Deleting Thing")
        client.delete_thing(thingName=THING_NAME)
        print("Deleting Thing Group")
        client.delete_thing_group(thingGroupName=GROUP_NAME)
        print("Deleting Policy")
        client.delete_policy(policyName=POLICY_NAME)
    else:
        print("Unable to find certificate id")

    if os.path.exists(CERTIFICATE_ID_FILE):
        os.remove(CERTIFICATE_ID_FILE)

    if os.path.exists(PRIVATE_KEY_FILE):
        os.remove(PRIVATE_KEY_FILE)

    if os.path.exists(CERTIFICATE_PEM_FILE):
        os.remove(CERTIFICATE_PEM_FILE)


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
            print("Created Certificate  arn:" + certificateArn + "\n id:" + response['certificateArn'])

            with open(CERTIFICATE_PEM_FILE, "w") as certificateFile:
                certificateFile.write(certificatePem)
                agent_args += ["-c", os.path.realpath(certificateFile.name)]

            # Save the certificate id to a file so we can easily cleanup later
            with open(CERTIFICATE_ID_FILE, "w") as certificateIdFile:
                certificateIdFile.write(response['certificateId'])

            with open(PRIVATE_KEY_FILE, "w") as private_key:
                private_key.write(keyPair["PrivateKey"])
                private_key
                agent_args += ["-k", os.path.realpath(private_key.name)]

            response = client.attach_thing_principal(thingName=THING_NAME, principal=certificateArn)
            print("Attached Certificate to Thing: " + THING_NAME)

            with open(IOT_POLICY_FILE, "r") as policyFile:
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
