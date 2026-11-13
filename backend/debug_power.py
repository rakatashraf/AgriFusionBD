import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.dev'
django.setup()

from apps.farms.models import Field
from apps.environment.services.power import _parse_payload, _store_indicators
import json

f = Field.objects.get(slug='north-paddy-plot')
print("Field:", f.name, f.lat, f.lng)

# Check the cached payload
from apps.environment.models import DataAsset
assets = DataAsset.objects.filter(field=f).order_by('-fetched_at')[:3]
print("DataAssets:", assets.count() if hasattr(assets, 'count') else len(list(assets)))
for a in list(assets):
    print("  asset:", a.cache_key, a.status, a.fetched_at)

# Try a direct live fetch
from apps.environment.services.power import get_daily_series
from datetime import datetime, timedelta
end = datetime.utcnow().strftime('%Y-%m-%d')
start = (datetime.utcnow() - timedelta(days=10)).strftime('%Y-%m-%d')
print("Fetching", start, "to", end)
result = get_daily_series(f.lat, f.lng, start, end, field_model=f)
print("Source:", result.source)
print("Rows:", len(result.rows))
if result.rows:
    r = result.rows[0]
    print("First row keys:", list(r.keys()))
    print("First row:", {k: r.get(k) for k in ['date','prectot','t2m','tmax','tmin','rh','ws','rs']})
    # Count non-null values
    for key in ['prectot','t2m','tmax','tmin','rh','ws','rs']:
        non_null = sum(1 for row in result.rows if row.get(key) is not None)
        print("  " + key + ":", non_null, "non-null of", len(result.rows))
