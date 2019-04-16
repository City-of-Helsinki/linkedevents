from django.apps import AppConfig

from .extension import CourseExtension


class ExtensionCourseConfig(AppConfig):
    name = 'extension_course'
    event_extension = CourseExtension
