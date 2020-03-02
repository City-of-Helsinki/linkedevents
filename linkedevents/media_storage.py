from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings


class MediaStorage(S3Boto3Storage):
    bucket_name = getattr(settings, 'AWS_MEDIA_STORAGE_BUCKET_NAME')
    default_acl = getattr(settings, 'AWS_MEDIA_DEFAULT_ACL')
    # The S3 files are served through nginx so we need to set the correct domain and path
    custom_domain = getattr(settings, 'AWS_MEDIA_S3_CUSTOM_DOMAIN')
