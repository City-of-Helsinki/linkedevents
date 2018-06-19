from events.extensions import EventExtension


class CourseExtension(EventExtension):
    identifier = 'course'
    related_name = 'extension_course'

    def get_extension_serializer(self):
        from .serializers import CourseSerializer
        return CourseSerializer()

    def post_create_event(self, request, event, data):
        from .models import Course
        course_data = data.get('extension_course', {})
        Course.objects.create(event=event, **course_data)

    def post_update_event(self, request, event, data):
        from .models import Course
        course_data = data.get('extension_course')
        if course_data is not None:
            Course.objects.update_or_create(event=event, defaults=course_data)
