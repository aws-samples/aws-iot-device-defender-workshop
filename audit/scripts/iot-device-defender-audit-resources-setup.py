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

import os
import sys
import uuid
import boto3
import atexit
import logging
import random
import textwrap
import string
import json
import tempfile
import base64
import binascii
import datetime
import hashlib
import hmac
import time
import botocore
import six
import argparse

from botocore.exceptions import ClientError
from datetime import datetime
from datetime import timedelta
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

class NullHandler(logging.Handler):
    def emit(self, record):
        pass

logger = logging.getLogger('aws-iot-device-defender-demo')
logger.setLevel(logging.INFO)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)

logger.addHandler(ch)

IOT_ROOT_CA_PATH = './resources/AWSIoTRootCA.pem'

parser = argparse.ArgumentParser(
    description = 'AWS IoT Device Defender Demo')
parser.add_argument('--region', required = True,
    help = 'Region this script is being running in')
parser.add_argument('--skip-cleanup', default = False, action = 'store_true',
    help = 'Flag to skip removal of AWS resources created for demo before exit')
args = parser.parse_args()

cleanup_required = not args.skip_cleanup

iot_client = boto3.client('iot', region_name=args.region)
s3_client = boto3.client('s3')

pki_bucket = 'device-defender-audit-demo-' + str(uuid.uuid4())
s3_client.create_bucket(Bucket=pki_bucket)

region = boto3.session.Session().region_name

one_day = timedelta(1, 0, 0)
one_year = timedelta(365, 0, 0)

cleanup_required = False

cleanup_ca_list = []
cleanup_cert_list = []
cleanup_policy_list = []
cleanup_default_log_level = 'DISABLED'


class CRLS3Publisher():

    def __init__(self, s3_bucket):
        self.s3_key = str(uuid.uuid4()) + '.crl'
        self.s3_bucket = s3_bucket

    def get_url(self):
        return 'http://s3.amazonaws.com/%s/%s' % (self.s3_bucket, self.s3_key)

    def publish(self, crl):
        s3_client.put_object(
            Bucket = self.s3_bucket,
            Key = self.s3_key,
            Body = crl.public_bytes(serialization.Encoding.PEM),
            ContentType = 'text/plain',
            ACL = 'public-read')

class CAS3Publisher():

    def __init__(self, s3_bucket):
        self.s3_key = str(uuid.uuid4()) + '.crt'
        self.s3_bucket = s3_bucket

    def get_url(self):
        return 'http://s3.amazonaws.com/%s/%s' % (self.s3_bucket, self.s3_key)

    def publish(self, ca_certificate):
        s3_client.put_object(
            Bucket = self.s3_bucket,
            Key = self.s3_key,
            Body = cert_to_pem(ca_certificate),
            ContentType = 'text/plain',
            ACL = 'public-read')

def cert_to_pem(certificate):
    return certificate.public_bytes(
        encoding = serialization.Encoding.PEM)

def privkey_to_pem(pkey):
    return pkey.private_bytes(
        encoding = serialization.Encoding.PEM,
        format = serialization.PrivateFormat.PKCS8,
        encryption_algorithm = serialization.NoEncryption())

def get_common_name(certificate):
    return certificate.subject.get_attributes_for_oid(
        NameOID.COMMON_NAME)[0].value

def get_rand_string(prefix = None, length = 8,
    join_char = "-", characters = string.lowercase):

    str = ''.join(random.choice(characters) for x in range(length))
    if prefix:
        str = prefix + join_char + str

    return str

def create_certificate(common_name, not_valid_before, not_valid_after,
    issuer_common_name = None, issuer_private_key = None,
    crl_distribution_point = None, authority_info_uri = None,
    is_ca_certificate = False):

    private_key = rsa.generate_private_key(
        public_exponent = 65537,
        key_size = 2048,
        backend = default_backend())

    public_key = private_key.public_key()

    if not issuer_common_name:
        issuer_common_name = common_name

    if not issuer_private_key:
        issuer_private_key = private_key
        is_ca_certificate = True

    builder = x509.CertificateBuilder()
    builder = builder.subject_name(x509.Name([
        x509.NameAttribute(
            NameOID.COMMON_NAME, unicode(common_name))]))

    builder = builder.issuer_name(x509.Name([
        x509.NameAttribute(
            NameOID.COMMON_NAME, unicode(issuer_common_name))]))

    builder = builder.not_valid_before(not_valid_before)
    builder = builder.not_valid_after(not_valid_after)
    builder = builder.serial_number(int(uuid.uuid4()))
    builder = builder.public_key(public_key)
    builder = builder.add_extension(
        x509.BasicConstraints(ca = is_ca_certificate, path_length = None),
        critical = True)

    if crl_distribution_point:
        builder = builder.add_extension(
            x509.CRLDistributionPoints([
                x509.DistributionPoint(
                    full_name = [
                        x509.UniformResourceIdentifier(
                            unicode(crl_distribution_point))
                    ],
                    relative_name = None,
                    reasons = None,
                    crl_issuer = None)
            ]),
            critical = True)

    if authority_info_uri:
        builder = builder.add_extension(
            x509.AuthorityInformationAccess([
                x509.AccessDescription(
                    access_method = \
                        x509.oid.AuthorityInformationAccessOID.CA_ISSUERS,
                    access_location = x509.UniformResourceIdentifier(
                        unicode(authority_info_uri))
                )
            ]),
            critical = True)

    certificate = builder.sign(
        private_key = issuer_private_key,
        algorithm = hashes.SHA256(),
        backend = default_backend())

    return private_key, certificate

def build_revocation_list(ca_private_key, ca_certificate, revoked_certificates):

    crl_builder = x509.CertificateRevocationListBuilder()
    crl_builder = crl_builder.issuer_name(ca_certificate.subject)
    crl_builder = crl_builder.last_update(datetime.utcnow())
    crl_builder = crl_builder.next_update(datetime.utcnow() + one_year)

    for revoked_certificate in revoked_certificates:
        entry_builder = x509.RevokedCertificateBuilder()
        entry_builder = entry_builder.serial_number(revoked_certificate.serial_number)
        entry_builder = entry_builder.revocation_date(datetime.utcnow())
        crl_builder = crl_builder.add_revoked_certificate(
            entry_builder.build(default_backend()))

    return crl_builder.sign(
        private_key = ca_private_key,
        algorithm = hashes.SHA256(),
        backend = default_backend())

def get_ca_registration_code():
    return iot_client.get_registration_code()['registrationCode']

def create_iot_ca_certificate(common_name,
    not_valid_before, not_valid_after,
    crl_distribution_point = None,
    authority_info_uri = None,
    issuer_common_name = None,
    issuer_private_key = None):

    ca_private_key, ca_certificate = \
        create_certificate(
            common_name = common_name,
            not_valid_before = not_valid_before,
            not_valid_after = not_valid_after,
            crl_distribution_point = crl_distribution_point,
            authority_info_uri = authority_info_uri,
            issuer_common_name = issuer_common_name,
            issuer_private_key = issuer_private_key,
            is_ca_certificate = True)

    ca_check_private_key, ca_check_certificate = \
        create_certificate(
            common_name = get_ca_registration_code(),
            not_valid_before = not_valid_before,
            not_valid_after = not_valid_after,
            issuer_common_name =  common_name,
            issuer_private_key = ca_private_key)

    ca_certificate_id = \
        iot_client.register_ca_certificate(
            caCertificate = cert_to_pem(ca_certificate),
            verificationCertificate = cert_to_pem(ca_check_certificate),
            setAsActive = True)['certificateId']

    cleanup_ca_list.append(ca_certificate_id)
    return ca_private_key, ca_certificate

def create_iot_certificate(common_name,
    issuer_certificate, issuer_private_key,
    not_valid_before, not_valid_after,
    crl_distribution_point = None):

    private_key, certificate = create_certificate(
        common_name = common_name,
        not_valid_before = not_valid_before,
        not_valid_after = not_valid_after,
        issuer_common_name =  get_common_name(issuer_certificate),
        issuer_private_key = issuer_private_key,
        crl_distribution_point = crl_distribution_point)

    registered_certificate = iot_client.register_certificate(
        certificatePem = cert_to_pem(certificate),
        caCertificatePem = cert_to_pem(issuer_certificate),
        setAsActive = True)

    cleanup_cert_list.append(registered_certificate['certificateId'])
    return private_key, certificate, registered_certificate['certificateArn']

def create_iot_policy(policy_name, policy_document):

    iot_client.create_policy(
        policyName = policy_name,
        policyDocument = json.dumps(policy_document))

    cleanup_policy_list.append(policy_name)

    return policy_name

def attach_iot_policy(certificate_arn, policy_name, policy_document):

    policy_name = create_iot_policy(
        policy_name = policy_name,
        policy_document = policy_document)

    iot_client.attach_policy(
        policyName = policy_name, target = certificate_arn)

    return policy_name

def demo_iot_ca_expiring_soon(
    demo_id = 'demo_iot_ca_expiring_soon'):

    logger.info(demo_id)

    not_valid_before = datetime.today() - one_day
    not_valid_after = datetime.today() + one_day

    create_iot_ca_certificate(
        common_name = get_rand_string(demo_id),
        not_valid_before = not_valid_before,
        not_valid_after = not_valid_after)

def demo_iot_ca_revoked(
    pki_bucket, demo_id = 'demo_iot_ca_revoked'):

    logger.info(demo_id)

    ca_s3_publisher = CAS3Publisher(s3_bucket = pki_bucket)

    root_ca_common_name = get_rand_string(demo_id)
    root_ca_private_key, root_ca_certificate = \
        create_certificate(
            common_name = root_ca_common_name,
            not_valid_before = datetime.today() - one_year,
            not_valid_after = datetime.today() + one_year)

    ca_s3_publisher.publish(root_ca_certificate)

    crl_s3_publisher = CRLS3Publisher(s3_bucket = pki_bucket)

    ca_private_key, ca_certificate = \
        create_iot_ca_certificate(
            common_name = get_rand_string(demo_id),
            not_valid_before = datetime.today() - one_day,
            not_valid_after = datetime.today() + one_year,
            issuer_common_name = root_ca_common_name,
            issuer_private_key = root_ca_private_key,
            crl_distribution_point = crl_s3_publisher.get_url(),
            authority_info_uri = ca_s3_publisher.get_url())

    crl = build_revocation_list(
        root_ca_private_key, root_ca_certificate, [ca_certificate])

    crl_s3_publisher.publish(crl)

def demo_iot_cert_expiring_soon(
    demo_id = 'demo_iot_cert_expiring_soon'):

    logger.info(demo_id)

    ca_private_key, ca_certificate = \
        create_iot_ca_certificate(
            common_name = get_rand_string(demo_id),
            not_valid_before = datetime.today() - one_day,
            not_valid_after = datetime.today() + one_year)

    create_iot_certificate(
        common_name = get_rand_string(demo_id),
        issuer_certificate = ca_certificate,
        issuer_private_key = ca_private_key,
        not_valid_before = datetime.today() - one_day,
        not_valid_after = datetime.today() + one_day)

def demo_iot_cert_revoked(
    pki_bucket, demo_id = 'demo_iot_cert_revoked'):

    logger.info(demo_id)

    ca_private_key, ca_certificate = \
        create_iot_ca_certificate(
            common_name = get_rand_string(demo_id),
            not_valid_before = datetime.today() - one_day,
            not_valid_after = datetime.today() + one_year)

    crl_s3_publisher = CRLS3Publisher(s3_bucket = pki_bucket)

    private_key, certificate, certificate_arn = \
        create_iot_certificate(
            common_name = get_rand_string(demo_id),
            issuer_certificate = ca_certificate,
            issuer_private_key = ca_private_key,
            not_valid_before = datetime.today() - one_day,
            not_valid_after = datetime.today() + one_year,
            crl_distribution_point = crl_s3_publisher.get_url())

    crl = build_revocation_list(
        ca_private_key, ca_certificate, [certificate])

    crl_s3_publisher.publish(crl)

def demo_iot_permissive_policy(
    demo_id = 'demo_iot_permissive_policy'):

    logger.info(demo_id)

    create_iot_policy(
        policy_name = get_rand_string(demo_id),
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": "iot:*",
                "Resource": "*"
            }]
        })

def demo_disable_iot_logging(
    demo_id = 'demo_disable_iot_logging'):

    logger.info(demo_id)

    global cleanup_default_log_level

    try:
        cleanup_default_log_level = \
            iot_client.get_v2_logging_options()['defaultLogLevel']
    except Exception, e:
        if e.response['Error']['Code'] == 'NotConfiguredException':
            cleanup_default_log_level = 'DISABLED'
        else:
            print "Unexpected error: %s" % e

    if cleanup_default_log_level != 'DISABLED':
        iot_client.set_v2_logging_options(
            defaultLogLevel = 'DISABLED', disableAllLogs = True)

@atexit.register
def cleanup():

    if cleanup_required:
        cleanup_iot_cas()
        cleanup_iot_certs()
        cleanup_iot_policies()
        cleanup_iot_logging_changes()

def cleanup_iot_cas():

    logger.info('Cleaning up IoT CAs')
    for ca_cert_id in cleanup_ca_list:
        try:
            iot_client.update_ca_certificate(
                certificateId = ca_cert_id,
                newStatus = 'INACTIVE')

            iot_client.delete_ca_certificate(
                certificateId = ca_cert_id)
        except Exception, e:
            logger.error('Failed deleteing CA certificate (Id:%s)' % ca_cert_id)

def cleanup_iot_certs():

    logger.info('Cleaning up IoT certificates')
    for cert_id in cleanup_cert_list:
        try:
            iot_client.update_certificate(
                certificateId = cert_id,
                newStatus = 'INACTIVE')

            iot_client.delete_certificate(
                certificateId = cert_id,
                forceDelete = True)
        except Exception, e:
            logger.error('Failed deleteing certificate (Id:%s)' % cert_id)

def cleanup_iot_policies():

    logger.info('Cleaning up IoT policies')
    for policy_name in cleanup_policy_list:
        try:
            targets = iot_client.list_targets_for_policy(
                policyName = policy_name)['targets']

            for target in targets:
                iot_client.detach_policy(
                    policyName = policy_name, target = target)

            iot_client.delete_policy(policyName = policy_name)
        except Exception, e:
            logger.error('Failed deleteing policy (Name:%s)' % policy_name)

def cleanup_iot_logging_changes():

    logger.info('Cleaning up IoT logging changes')
    if cleanup_default_log_level != 'DISABLED':
        iot_client.set_v2_logging_options(
            defaultLogLevel = cleanup_default_log_level,
            disableAllLogs = False)

logger.info('Setting up device defender demo...')

demo_iot_cert_expiring_soon()
demo_iot_cert_revoked(pki_bucket)
demo_iot_ca_expiring_soon()
demo_iot_ca_revoked(pki_bucket)
demo_iot_permissive_policy()
demo_disable_iot_logging()

if cleanup_required:
    raw_input('\nPress enter to exit and cleanup...')
