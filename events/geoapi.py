from django.contrib.gis.db import models
from rest_framework import serializers
from rest_framework.exceptions import ParseError
from django.contrib.gis.gdal import CoordTransform, SpatialReference
from django.contrib.gis.geos import Point, Polygon
import json

# Use the GPS coordinate system by default
DEFAULT_SRID = 4326

def poly_from_bbox(bbox_val):
    points = bbox_val.split(',')
    if len(points) != 4:
        raise ParseError("bbox must be in format 'left,bottom,right,top'")
    try:
        points = [float(p) for p in points]
    except ValueError:
        raise ParseError("bbox values must be floating points or integers")
    poly = Polygon.from_bbox(points)
    return poly

def srid_to_srs(srid):
    if not srid:
        srid = DEFAULT_SRID
    try:
        srid = int(srid)
    except ValueError:
        raise ParseError("'srid' must be an integer")
    try:
        srs = SpatialReference(srid)
    except SRSException:
        raise ParseError("SRID %d not found (try 4326 for GPS coordinate system)" % srid)
    return srs

def build_bbox_filter(srs, bbox_val, field_name):
    poly = poly_from_bbox(bbox_val)
    poly.set_srid(srs.srid)

    return {"%s__within" % field_name: poly}


class GeoModelSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super(GeoModelSerializer, self).__init__(*args, **kwargs)
        model = self.opts.model
        self.geo_fields = []
        model_fields = [f.name for f in model._meta.fields]
        for field_name in self.fields:
            if not field_name in model_fields:
                continue
            field = model._meta.get_field(field_name)
            if not isinstance(field, models.GeometryField):
                continue
            self.geo_fields.append(field_name)
            del self.fields[field_name]

        # SRS is deduced in ViewSet and passed from there
        self.srs = self.context.get('srs', None)

    def to_native(self, obj):
        ret = super(GeoModelSerializer, self).to_native(obj)
        if obj is None:
            return ret
        for field_name in self.geo_fields:
            val = getattr(obj, field_name)
            if val == None:
                ret[field_name] = None
                continue
            if self.srs:
                if self.srs.srid != val.srid:
                    ct = CoordTransform(val.srs, self.srs)
                    val.transform(ct)

            s = val.geojson
            ret[field_name] = json.loads(s)
        return ret
