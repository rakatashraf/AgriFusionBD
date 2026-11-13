import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.dev'
django.setup()

from apps.farms.models import Field
from apps.environment.models import DataAsset, FieldIndicator
from django.contrib.gis.geos import Polygon, Point

RAJ_LNG = 88.60
RAJ_LAT = 24.37
fields_cfg = [
    ('north-paddy-plot', RAJ_LAT, RAJ_LNG, 0.004, 0.004),
    ('pin-estimate-plot', RAJ_LAT - 0.012, RAJ_LNG - 0.015, 0, 0),
    ('river-bend', RAJ_LAT + 0.010, RAJ_LNG + 0.022, 0.004, 0.004),
]
for slug, lat, lng, w, h in fields_cfg:
    f = Field.objects.get(slug=slug)
    f.lat = lat
    f.lng = lng
    if w > 0:
        ring = [
            (lng - w/2, lat - h/2),
            (lng + w/2, lat - h/2),
            (lng + w/2, lat + h/2),
            (lng - w/2, lat + h/2),
            (lng - w/2, lat - h/2),
        ]
        f.geometry = Polygon(ring)
    else:
        f.geometry = Point(lng, lat)
    f.save()
    print("Updated " + f.name + ": lat=" + str(lat) + ", lng=" + str(lng))

deleted, _ = DataAsset.objects.filter(cache_key__contains='power').delete()
print("Deleted " + str(deleted) + " POWER cache entries")

deleted_ind, _ = FieldIndicator.objects.filter(kind__in=['rainfall','temperature','ndvi','rs']).delete()
print("Deleted " + str(deleted_ind) + " old indicator rows")
