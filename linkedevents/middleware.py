from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class AwsAlbHeaderMiddleware(MiddlewareMixin):
    def _transform_header_to_django_format(self, header):
        return 'HTTP_{}'.format(header.upper().replace('-', '_'))

    def process_request(self, request):
        """Replaces X-Forwarded-{Port|Proto} headers with values from other custom headers

        AWS load balancers overwrite the X-Forwarded-{Port|Proto} headers so setting them in a reverse proxy has no
        effect. To overcome this, we can set custom headers in the reverse proxy and copy the X-Forwarded-{Port|Proto}
        header values from these custom headers.

        See https://docs.aws.amazon.com/elasticloadbalancing/latest/classic/x-forwarded-headers.html.

        You can define the custom header names as environment variables, e.g.:

            CUSTOM_X_FORWARDED_PORT_HEADER=LINKEDEVENTS-X-FORWARDED-PORT
            CUSTOM_X_FORWARDED_PROTO_HEADER=LINKEDEVENTS-X-FORWARDED-PROTO

        The middleware will take care of transforming the header names to forms understood by Django, e.g.:

            LINKEDEVENTS-X-FORWARDED-PORT -> HTTP_LINKEDEVENTS_X_FORWARDED_PORT
            LINKEDEVENTS-X-FORWARDED-PROTO -> HTTP_LINKEDEVENTS_X_FORWARDED_PROTO
        """
        custom_x_forwarded_port_header = getattr(settings, 'CUSTOM_X_FORWARDED_PORT_HEADER')
        if custom_x_forwarded_port_header:
            corrected_x_forwarded_port_header = self._transform_header_to_django_format(custom_x_forwarded_port_header)
            x_forwarded_port = request.META.get(corrected_x_forwarded_port_header, '')
            request.META['HTTP_X_FORWARDED_PORT'] = x_forwarded_port

        custom_x_forwarded_proto_header = getattr(settings, 'CUSTOM_X_FORWARDED_PROTO_HEADER')
        if custom_x_forwarded_proto_header:
            corrected_x_forwarded_proto_header = self._transform_header_to_django_format(
                custom_x_forwarded_proto_header
            )
            x_forwarded_proto = request.META.get(corrected_x_forwarded_proto_header, '')
            request.META['HTTP_X_FORWARDED_PROTO'] = x_forwarded_proto
