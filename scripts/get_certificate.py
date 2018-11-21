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
import argparse


def parse_args():
    parser = argparse.ArgumentParser(fromfile_prefix_chars="@")
    parser.add_argument("-i", "--certificate-id", action="store", required=True, dest="certificate_id",
                        help="Certificate Id, can be obtained, the Iot console")

    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()

    client = boto3.client('iot')

    response = client.describe_certificate(certificateId=args.certificate_id)
    certificate_pem = response["certificateDescription"]["certificatePem"]

    with open("../certificates/certificate.pem", "w") as certificate_file:
        certificate_file.write(certificate_pem)
