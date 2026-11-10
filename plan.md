# FieldShift — NASA Space Apps 2026 Implementation Plan

**Challenge:** [Field Shift: Adapting Farms with NASA Data](https://www.spaceappschallenge.org/2026/challenges/adapting-farms-with-nasa-data/)
**Event:** Bangladesh, 13–14 Nov 2026 (global window 14–15 Nov)
**Repo root:** `D:\Nasa` · existing UI in `D:\Nasa\frontend`

**Chosen architecture: Hybrid — keep the TanStack Start UI, build the Django/DRF backend from the report, connect them over HTTP.**

The report (`FieldShift_Project_Report_and_Architecture.docx`, Design baseline 1.0, 6 Nov 2026) specifies SvelteKit + Django + PostGIS + Celery/Redis. The UI already exists in TanStack Start and is the most finished asset; rewriting it in SvelteKit before the event is not defensible. Everything below the UI — app layout, models, REST contract, engine, ingestion, jobs, provenance — follows the report. The report remains the design north star; the README documents the delivered subset and the one deliberate deviation (TanStack instead of SvelteKit).

---

## 1. Goal

Turn the existing **clickable design baseline** (12 routes, fully mocked data) into a **working, judge-ready, NASA-data-first decision-support tool** that demos offline on stage and scores well on Impact, Creativity, Validity, Relevance and Presentation.

Pitch to protect:

> FieldShift compares a farmer's actual rotation against two locally feasible alternatives using NASA POWER climate data, HLS vegetation indices, local soil tests, crop traits and the farmer's own weights — and shows every assumption, gap and data source behind the score.

Non-negotiables from the report:
- Three sequences: the real baseline + up to two alternatives, with reasons.
- If the evidence cannot support two alternatives, **explain the limitation instead of fabricating options** (§7).
- Historical observations, scenarios, forecasts and rover readings stay visually and semantically distinct.
- Every displayed indicator carries observation period, units and coverage status (§12).

---

## 2. Audit of what exists

**Frontend (done, mocked):** TanStack Start + React 19 + Vite 8 + Tailwind 4 + Base UI/shadcn + MapLibre GL 6 + ECharts 6, bilingual EN/BN. Routes: `/`, `/farmer/fields`, `/farmer/fields/$fieldId`, `/farmer/analyses[/new|/$analysisId]`, `/farmer/cases`, `/farmer/rover`, `/professional/{cases,research,jobs}`.

**Already aligned with the report:**
- `src/lib/types.ts` mirrors §8 closely and is the JSON contract the Django serializers must emit.
- `src/lib/api.ts` already uses the §9 endpoint paths behind `VITE_API_BASE`.
- UI already renders `warnings`, `assumptions`, `missingData`, per-metric `qualification`, `feasibility`, `stale`, coverage % and the `insufficient` state.
- MapLibre + ECharts match §4 exactly.

**Missing:** the entire backend, persistence, real NASA data, the engine, auth/sessions, exports, and provenance.

**Defects to fix in passing:**
- `src/routes/index.tsx`: Bangla typo `khảবহ` → `বাস্তবায়নযোগ্য`.
- `api.ts` `currentUser()` hardcodes the farmer; workspace switch is cosmetic. Replace with a real Django session and a visible "demo identity" selector.
- `__root.tsx` ships TanStack Devtools in production — gate on `import.meta.env.DEV`.
- Analysis detail polls forever every 1.5 s; stop on terminal status.
- `createExportJob` creates no downloadable artifact.
- Accept/Question/Reject and "Open officer case" are inert.
- `search: { fieldId: '' } as never` hides route type errors — clean up as routes are touched.

---

## 3. Architecture

```
Browser (TanStack Start UI, no business logic)
        │  HTTPS, session cookie + CSRF
        ▼
nginx  ── /      → node:3000 (TanStack/Nitro SSR)
       └─ /api/  → gunicorn:8000 (Django + DRF)
                        │
        ┌───────────────┼────────────────┐
        ▼               ▼                ▼
  PostgreSQL+PostGIS   Redis        media/ (object storage in prod)
        ▲               ▲
        └── Celery worker + Beat (optional profile; eager by default)
```

- **One public origin** in every environment (nginx locally via Compose; Vite proxy in dev). The report requires this for secure cookies and CSRF (§2, §11).
- **Django is the only authority** for authentication, permissions and agronomic logic (§4: "Do not duplicate agricultural logic in the frontend").
- **PostgreSQL + PostGIS** is the source of truth (§8). Use `postgis/postgis:16-3.4` from Compose; if Docker is unavailable, point `DATABASE_URL` at a hosted PostGIS (Supabase/Neon) rather than falling back to SQLite — geometry is a core part of the design, not a nice-to-have.
- **Celery/Redis is wired but eager by default.** The engine runs in well under a second, so `CELERY_TASK_ALWAYS_EAGER=True` in dev guarantees the demo never depends on a broker. The Compose `workers` profile enables the real Redis + worker path for the "production" story and heavy HLS ingestion.
- **Files:** local `MEDIA_ROOT` for the pilot; storage is behind a Django `Storage` setting so S3 can drop in.

**Repo layout**

```
D:\Nasa\
  backend\
    manage.py
    config\{settings\{base,dev,prod}.py,urls.py,asgi.py,wsgi.py}
    apps\{accounts,farms,catalogue,environment,analyses,cases,rovers,research,audit}\
    fixtures\seed.json + fixtures\nasa\
    requirements.txt  pytest.ini  .env.example
  frontend\            (existing app, UI only)
  scripts\             (dev.ps1, demo.ps1, ingest_hls.py)
  docker-compose.yml   (postgis, redis, backend, frontend, nginx)
  nginx\default.conf
```

---

## 4. Work plan

### Phase 0 — Event readiness (before 13 Nov)

- [ ] Confirm **both** registrations: Bangladesh pre-registration (Local Lead) **and** the NASA team page. Global judges only see the NASA page.
- [ ] Create a free **NASA Earthdata Login**; store credentials/token in `.env` or `.netrc`, never in git.
- [ ] Pre-download the demo data (venue Wi-Fi must not be a dependency):
  - POWER daily JSON per pilot point, 2016-01-01 → today.
  - HLS L30/S30 scenes, 2 seasons; compute NDVI offline.
  - Commit only the small derived JSON under `backend/fixtures/nasa/`, not GeoTIFFs.
- [ ] Make the repo public + README with architecture diagram, data lineage and run instructions.
- [ ] Rehearse offline with the demo laptop in airplane mode.

### Phase 1 — Django foundation (report milestone 1)

Create the project and eight apps. Only the fields the UI and engine need are exercised; the rest of §8's schema ships as models/migrations so the design is visible in the repo.

| App | Models |
|---|---|
| `accounts` | `User` (custom, email login), `Organization`, `Membership`, `FieldGrant`, `Consent`, `AuditEvent` |
| `farms` | `Farm`, `Field` (versioned boundary, GeoDjango `PolygonField` srid=4326), `CropHistory`, `ManagementEvent` |
| `catalogue` | `Crop`, `Variety`, `CropRuleVersion`, `CropCalendar`, `SoilTest` |
| `environment` | `DatasetProduct`, `DataAsset`, `FieldIndicator` (unique provider/product/version/space/time) |
| `analyses` | `AnalysisRun`, `Scenario`, `RotationPlan`, `Metric`, `InputSnapshot` |
| `cases` | `AssistanceCase`, `CaseMessage`, `CaseReview` |
| `rovers` | `Device`, `DeviceGrant`, `SensorCalibration`, `Mission`, `Observation` |
| `research` | `ResearchProject`, `ExportJob` |

Decisions:
- `AnalysisRun` and its outbox event are written in one transaction (§8). The outbox dispatcher can be a management command for the pilot.
- Completed runs store the **frozen input snapshot** (POWER asset ids/hashes, HLS asset ids, catalogue version, rule version) so a rerun is reproducible.
- A pin-only field is stored with `is_pin_estimate=True` and a radius, never as a fabricated polygon.
- Seed command `python manage.py seed_demo` loads three pilot fields, six crops, soil tests, history and devices (reuse the values in `frontend/src/lib/mock-data.ts` for the fixture).

**Auth/session.** Django session auth, `SESSION_COOKIE_HTTPONLY`, `CSRF_COOKIE_HTTPONLY=False` (the SPA must read it), `SameSite=Lax`, `Secure` in prod. Demo endpoints:
- `POST /api/v1/auth/login/` `{role}` → session for a seeded demo user.
- `POST /api/v1/auth/logout/`
- `GET /api/v1/auth/me/`

Roles are enforced **server-side** on every object query. The workspace toggle calls the login endpoint; it must not be a client-only flag (§2).

### Phase 2 — API contract (report §9)

Implement with DRF `ModelViewSet`s + `drf-spectacular`. Required endpoints, plus what the UI calls:

```
GET/POST      /api/v1/fields
GET/PATCH     /api/v1/fields/{id}
PATCH         /api/v1/fields/{id}/profile
GET           /api/v1/fields/{id}/crop-history
GET           /api/v1/fields/{id}/soil-tests
GET           /api/v1/fields/{id}/indicators
POST          /api/v1/fields/{id}/analyses          → 202 + run, honours Idempotency-Key
GET           /api/v1/analyses/{id}
GET           /api/v1/analyses/{id}/evidence
POST          /api/v1/analyses/{id}/cancel
GET/POST      /api/v1/cases
PATCH         /api/v1/cases/{id}                    (accept / question / reject)
POST          /api/v1/cases/{id}/messages
GET           /api/v1/devices
GET           /api/v1/observations?field=
POST          /api/v1/devices/{id}/observations     (device token, dedupe message_id)
GET           /api/v1/research/locations
GET/POST      /api/v1/research/exports
GET           /api/v1/research/exports/{id}/download
GET           /api/v1/catalogue/crops
```

Contract rules:
- Stable error shape `{ "error": { "code", "message", "details" } }` (report §9).
- Bounded geometry/date ranges, pagination, `updated_at` optimistic concurrency on PATCH.
- Every indicator response includes period, units, coverage and asset id.
- Every completed analysis includes `rule_version`, snapshot ids and `warnings`.
- OpenAPI at `/api/schema/`, docs at `/api/docs/`.

### Phase 3 — NASA data layer (report §6)

`apps/environment/services/power.py`
- `https://power.larc.nasa.gov/api/temporal/daily/point`, `community=AG`, params `PRECTOTCORR,T2M,T2M_MAX,T2M_MIN,RH2M,WS2M,ALLSKY_SFC_SW_DWN`.
- Cache key = provider + product + parameters + rounded cell + dates + time standard. Persisted as a `DataAsset` with content hash; TTL 7 days.
- Retries: 3, exponential backoff + jitter, capped; 10 s timeout. Auth errors are operational faults, not cache misses. **Never replace missing rainfall with zero** (§6).
- On total failure: serve the seeded snapshot with `stale=true`; if no snapshot exists, return `partial` evidence.

`apps/environment/services/hls.py`
- Runtime reads the committed NDVI series (from `scripts/ingest_hls.py`).
- `NDVI = (NIR − Red)/(NIR + Red)`; L30 B5/B4, S30 B8/B4; 30 m.
- Preserve acquisition dates; never invent daily cloud-free values; cloudy pixels never count as bare field. Valid-coverage threshold 40 %; below it → `quality: "missing"`.

`scripts/ingest_hls.py` (run pre-event)
- `earthaccess` + `rioxarray`, `--bbox --start --end --out`, writes JSON + manifest (scene ids, dates, cloud %, coverage %). The manifest becomes `DataAsset` rows.

Optional but high demo value: NASA **GIBS** WMTS NDVI layer in `FieldMap` — one public URL, no auth, visible NASA imagery on screen.

### Phase 4 — Rotation engine (report §7)

`apps/analyses/engine/` — pure functions, no ORM, dataclass inputs:

| Module | Calculation |
|---|---|
| `et0.py` | FAO-56 Penman-Monteith daily ET₀ from POWER Tmax/Tmin/RH/WS/RS |
| `water_balance.py` | Effective rainfall (USDA-SCS), `ETc = Kc × ET0`, soil bucket, irrigation demand, dry spells; paddy field-water term |
| `heat.py` | Historical Tmax aligned to crop development windows; threshold days at flowering/grain-fill, scaled by crop heat tolerance |
| `cover.py` | Canopy-cover fraction from calendar, corrected by HLS NDVI where coverage is adequate; tag inferred vs observed |
| `diversity.py` | Unique families, repetition, legume inclusion, break-crop vs last 2 years |
| `economics.py` | Net-margin **range** from yield × price − cost, with sensitivity |
| `candidates.py` | Enumerate rotations from reviewed calendars; hard filters (season overlap, irrigation limit, soil range, equipment, farmer exclusions); cap ~50 |
| `score.py` | Normalize against declared bounds, weighted `Σwᵢsᵢ/Σwᵢ`, feasibility + reasons independent of weights |
| `rules.py` | `RULE_VERSION = "v2026.11.0"` + git sha; Kc tables, thresholds, bounds |
| `runner.py` | `run(field, request, power, hls, catalogue) → {plans, warnings, evidence}` |

Behavioural rules:
- **Baseline is never invented** — it is the farmer's last rotation from `CropHistory`, extended into the requested season.
- Exactly two alternatives, highest weighted score among feasible candidates, each materially different from baseline (≥ 1 different family).
- Fewer than two feasible → `status="partial"` (or the `insufficient` evidence state) with `missing_data` explaining why. A validity win, not a failure.
- `Metric.raw_value` + `qualification` on every metric, e.g. "Reference ET × crop coefficients; canal efficiency 70 %; paddy field-water term included".
- Ranking is shown **after** the trade-off comparison; expose whether small weight changes flip the preferred plan (§7).
- No ML in the scoring path. ML is only justified after a target, protocol and ground truth exist (§7).

### Phase 5 — Frontend wiring

`frontend/src/lib/api.ts`
- `API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1'`; always `credentials: 'include'`.
- On unsafe methods, read the `csrftoken` cookie and send `X-CSRFToken`.
- Parse the Django error envelope into the existing toast messages.
- Delete every `mock-data` import and the `API_BASE === null` branch. Keep function signatures so route components barely change.

`frontend/vite.config.ts` — dev proxy `'/api' → http://localhost:8000`, so dev is same-origin and cookies/CSRF behave exactly like production.

Add:
- `/login` route: role picker (Farmer / Officer / Researcher) → `POST /auth/login/`; the AppShell workspace switch calls the same endpoint. Show the active demo identity in the header.
- Analysis polling with a terminal-state stop; remove fake timers.
- `FieldDraw` component for boundary/pin capture (MapLibre click + radius is enough; add `terra-draw` only if the click path is done early).
- `/method` route for judges: dataset lineage, equations, bounds, failure modes, limitations, rule version. Link from footer and every evidence card.
- Export button performs a real download from `/research/exports/{id}/download` (CSV/GeoJSON + `provenance.json`).
- Wire Accept / Question / Reject and "Open officer case".

Frontend must contain **no agronomic logic** — only presentation and input collection.

### Phase 6 — Reliability, tests, and submission

- **pytest + pytest-django**: engine determinism (same frozen inputs → identical output hash), baseline matches history, exclusions respected, insufficient-evidence path, PostGIS area validation, idempotency replay, permission matrix (cross-farmer read/write/export denied).
- **Contract tests** for `/fields/{id}/analyses` 202 + polling to complete, and `/research/exports/{id}/download` provenance.
- **Playwright smoke**: login → fields → comparison → evidence → export.
- Offline drill: block outbound network, confirm cached snapshots render with `stale` badges and no unhandled errors.
- Bilingual pass on every new string; 390 px + desktop; keyboard pass on the map and trade-off table.
- `python manage.py check --deploy`; `npm run build`; Compose boots clean from scratch.
- Submission: public repo, NASA project page (summary, demo, datasets + what each was used for, tools, references, **Use of AI** disclosure), 30 s video, 240 s cut with NASA datasets named on camera, English subtitles. Treat the run-of-show time (13 Nov, 18:30 for the local cut) as the working deadline and confirm with the Local Lead.

---

## 5. Scientific method (state it exactly, everywhere)

1. Pull daily POWER series for the field's coordinate (0.5° cell — label it as coarse cell data, not farm truth).
2. Compute ET₀ (FAO-56), effective rainfall, ETc with crop coefficients, and soil-water balance with a declared bucket capacity.
3. Score each candidate rotation on the five declared metrics; normalize against catalogue bounds; weight by the farmer's sliders.
4. Apply hard constraints → `feasible | constrained | infeasible` with reasons.
5. Emit baseline + up to two alternatives, warnings, assumptions, missing data, asset manifest, rule version.
6. If evidence is thin, say so and withhold alternatives.

Citations for `/method`: FAO-56 (Allen et al., 1998); HLS (Claverie et al., 2018); NASA POWER (NASA LaRC); Tiemann et al. (2015) on rotation diversity; DAE/BARC crop calendars and local price/cost ranges.

---

## 6. File map (critical paths)

```
backend/apps/
  accounts/{models,serializers,views,urls}.py
  farms/{models,serializers,views,urls}.py
  catalogue/{models,serializers,views}.py
  environment/models.py services/{power,hls,cache,provenance}.py
  analyses/models.py engine/{et0,water_balance,heat,cover,diversity,economics,candidates,score,rules,runner}.py
  cases/ rovers/ research/ audit/
backend/config/{settings/{base,dev,prod}.py,urls.py}
backend/fixtures/{seed.json,nasa/}
scripts/{ingest_hls.py,dev.ps1,demo.ps1}
docker-compose.yml  nginx/default.conf

frontend/src/lib/api.ts                      (rewrite: Django base, CSRF, credentials)
frontend/vite.config.ts                      (add /api proxy)
frontend/src/routes/login.tsx                (new)
frontend/src/routes/method.tsx               (new)
frontend/src/components/fields/FieldDraw.tsx (new)
frontend/src/routes/__root.tsx               (gate devtools)
frontend/src/routes/index.tsx                (Bangla typo)
```

Python deps: `Django`, `djangorestframework`, `drf-spectacular`, `psycopg[binary]`, `celery[redis]`, `requests`, `shapely`, `pyproj`, `pytest`, `pytest-django`. Frontend deps: none required for the core path; `terra-draw` only if time allows.

---

## 7. Verification / demo runbook

```powershell
# terminal 1 — data + API
docker compose up -d postgis redis
cd backend
python -m venv .venv; .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 8000
```

```powershell
# terminal 2 — UI (proxies /api → :8000)
cd frontend
npm run dev
```

Checks:
1. `curl localhost:3000/api/v1/fields` returns seeded fields through the proxy.
2. Login as farmer → `/farmer/fields` shows real geometry.
3. Submit a comparison twice → same `rule_version`, same plan ordering, one persisted run per idempotency key.
4. Drag `waterEfficiency` 0.1 → 0.7, resubmit → ranking changes with stated reasons (the demo money-shot).
5. Field with no soil test + < 40 % HLS coverage → `partial` with populated `missing_data`.
6. Disable network → snapshots render with `stale`; no crash.
7. Export → CSV downloads with a provenance manifest listing asset versions and rule version.
8. `pytest` green; `python manage.py check --deploy`; `npx tsc --noEmit`; `npm run build`.

**Judge walkthrough (3 min):** field map → add pin → field detail with NASA evidence → request comparison with sliders → trade-off matrix → evidence/method page → open officer case → export with provenance.

---

## 8. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Docker/PostGIS unavailable on the demo laptop | Point `DATABASE_URL` at hosted PostGIS (Supabase/Neon); same migrations |
| Earthdata auth or HLS download fails | Use committed NDVI snapshots; label retrieval dates and coverage; GIBS overlay as visual evidence |
| Venue network dies | Seeded POWER snapshot + `stale` badge; engine and API run locally |
| Redis/Celery misbehaves | `CELERY_TASK_ALWAYS_EAGER=True` (default) — engine runs inline; workers only for the production narrative |
| CORS/CSRF/cookie friction | Always demo through the single-origin proxy (Vite dev proxy, nginx in Compose); never cross-origin |
| Engine returns < 2 alternatives | Present the `insufficient` state deliberately — the report requires it |
| Teams demo generic "AI crop advisors" | Differentiator is auditable baseline-vs-alternatives with explicit gaps; no LLM in the decision path |

---

## 9. Out of scope

- Full consent management UI, MFA, Django Channels/WebSockets (polling is the MVP per §9).
- Remote rover driving, autonomous navigation, mission control (report §10 gates them behind separate safety testing).
- Forecast provider integration (post-MVP per §6).
- Kubernetes/multi-host scaling (§11 explicitly calls it conditional, not MVP).
- SvelteKit migration — documented as the one deviation from the report.

---

## 10. Definition of done

1. UI reads exclusively from Django; `mock-data.ts` is seed input only.
2. Baseline + up to two alternatives are produced by the Python engine, with reasons, warnings, gaps and a rule version.
3. NASA POWER is fetched live and cached; HLS NDVI is real, dated and coverage-labelled.
4. Analyses are reproducible from a frozen `InputSnapshot`; duplicate submissions collapse via idempotency.
5. Export downloads real data + provenance manifest.
6. The full flow demos offline, and the same flow works live.
7. Public repo, complete NASA project page, and both videos submitted before the local deadlines.
