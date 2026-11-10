"""
Environment: dataset products, data assets (cached NASA payloads), and the
field indicator series the UI charts.

``DataAsset`` is the cache unit for POWER/HLS payloads (content-hashed, with
a TTL). ``FieldIndicator`` is the time series the frontend renders, with the
period/units/coverage the report requires on every indicator (report §12).
"""

from django.db import models


class DatasetProduct(models.Model):
    """A catalogued NASA product (POWER, HLS L30, HLS S30, GIBS...)."""

    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    provider = models.CharField(max_length=80)  # NASA POWER | USGS HLS | NASA GIBS
    product_id = models.CharField(max_length=120)  # e.g. "POWER", "HLSL30.VI"
    resolution = models.CharField(max_length=40, blank=True)  # "0.5 deg" | "30 m"
    cadence = models.CharField(max_length=40, blank=True)  # "daily" | "16-day"
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class DataAsset(models.Model):
    """
    A cached, content-hashed payload from a provider.

    The cache key is provider + product + parameters + rounded cell + date
    range + time standard (plan §3, Phase 3). ``content_hash`` is a SHA-256 of
    the stored payload so a rerun can prove reproducibility.
    """

    STATUS_CHOICES = [
        ("fresh", "Fresh (fetched this session)"),
        ("cached", "Cached (within TTL)"),
        ("stale", "Stale (fallback, network unavailable)"),
    ]

    product = models.ForeignKey(DatasetProduct, on_delete=models.CASCADE, related_name="assets")
    field = models.ForeignKey("farms.Field", null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="data_assets")
    cache_key = models.CharField(max_length=255, unique=True)
    content_hash = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="fresh")
    acquired_at = models.DateTimeField()  # when the upstream data was acquired
    fetched_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    payload = models.JSONField(default=dict)  # the actual series / stats
    metadata = models.JSONField(default=dict, blank=True)  # scene ids, coverage %, etc.

    class Meta:
        ordering = ["-fetched_at"]
        indexes = [
            models.Index(fields=["product", "field", "acquired_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.product.name} · {self.cache_key[:48]}"


class FieldIndicator(models.Model):
    """
    One point on a field indicator series (rainfall, temperature, NDVI...).

    Every row carries the observation period, units and coverage so the UI can
    label it (report §12). ``is_forecast`` keeps scenarios/forecasts distinct
    from historical observations (report §1 non-negotiable).
    """

    KIND_CHOICES = [
        ("rainfall", "Rainfall"),
        ("temperature", "Temperature"),
        ("temperature_max", "Temperature max"),
        ("temperature_min", "Temperature min"),
        ("relative_humidity", "Relative humidity"),
        ("wind_speed", "Wind speed"),
        ("shortwave_radiation", "Shortwave radiation"),
        ("ndvi", "NDVI"),
    ]

    field = models.ForeignKey("farms.Field", on_delete=models.CASCADE, related_name="indicators")
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    asset = models.ForeignKey(DataAsset, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="indicators")
    provider = models.CharField(max_length=80, default="NASA POWER")
    product = models.CharField(max_length=120, default="POWER")
    version = models.CharField(max_length=32, default="v7")

    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    value = models.FloatField()
    unit = models.CharField(max_length=16)  # "mm" | "°C" | "fraction"
    coverage_pct = models.FloatField(default=100.0)
    quality = models.CharField(max_length=16, default="valid")  # valid | partial | missing
    is_forecast = models.BooleanField(default=False)
    is_inferred = models.BooleanField(default=False)  # e.g. calendar-derived cover

    # Unique per provider/product/version/space/time (plan §1, Phase 1).
    class Meta:
        unique_together = ("field", "kind", "provider", "product", "version", "period_start")
        ordering = ["period_start"]
        indexes = [models.Index(fields=["field", "kind", "period_start"])]

    def __str__(self):
        return f"{self.field.name} {self.kind} {self.period_start:%Y-%m-%d} = {self.value}"
