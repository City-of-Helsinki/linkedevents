from django.db.models import QuerySet


class AuditLogApiViewMixin:
    def _add_audit_logged_object_ids(self, instances):
        request = getattr(self.request, "_request", self.request)
        audit_logged_object_ids = set()

        def add_instance(instance):
            if not hasattr(instance, "pk") or not instance.pk:
                return

            audit_logged_object_ids.add(instance.pk)

        if isinstance(instances, QuerySet) or isinstance(instances, list):
            for instance in instances:
                add_instance(instance)
        else:
            add_instance(instances)

        if hasattr(request, "_audit_logged_object_ids"):
            request._audit_logged_object_ids.update(audit_logged_object_ids)
        else:
            request._audit_logged_object_ids = audit_logged_object_ids

    def get_object(self, skip_log_ids=False):
        instance = super().get_object()

        if not skip_log_ids:
            self._add_audit_logged_object_ids(instance)

        return instance

    def paginate_queryset(self, queryset):
        page = super().paginate_queryset(queryset)

        logged_objects = page if page is not None else queryset
        self._add_audit_logged_object_ids(logged_objects)

        return page

    def perform_create(self, serializer):
        super().perform_create(serializer)

        self._add_audit_logged_object_ids(serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)

        self._add_audit_logged_object_ids(serializer.instance)

    def perform_destroy(self, instance):
        self._add_audit_logged_object_ids(instance)

        super().perform_destroy(instance)
