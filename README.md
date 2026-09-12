# Registered-Individual Identification System

A small, complete web application for registering individuals with a few
face photos and later identifying them in real time through a browser
camera. Built for the Embsys Intelligence take-home assignment.

## Quick start

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt

# optional: copy backend/.env.example to backend/.env and edit ADMIN_TOKEN
export ADMIN_TOKEN=change-me-admin-token

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open **http://localhost:8000** in a browser (camera access requires
`localhost` or HTTPS - both satisfy the browser's secure-context rule for
`getUserMedia`).

- `/register` - admin registers a new individual with 3-5 face captures
- `/identify` - public camera view; polls for a match every ~1.5s
- `/manage` - admin views the roster and removes individuals

The admin pages ask for the `ADMIN_TOKEN` value once and store it in
`localStorage`, then send it as an `X-Admin-Token` header on every
admin request.

No separate database setup step is needed - SQLite is created
automatically at `backend/data/app.db` on first run, along with a
`backend/data/faces/` directory holding the normalized face crops used to
train the recognizer.

## Demonstration walkthrough

1. Open `/register`, enter an admin token, start the camera, capture 3-5
   photos of a person from slightly different angles, fill in their name
   and details, and click **Register individual**.
2. Open `/identify`, start the camera, and have that same person stand in
   frame. Within ~1.5s the result panel shows their name and stored
   details. Have someone unregistered stand in frame instead - the panel
   shows "Not identified."
3. Open `/manage` (with the admin token) to see everyone registered and
   to remove someone; the recognizer immediately retrains and forgets
   them.

## Architecture

```
Browser (register.html / identify.html / manage.html)
    | fetch() with multipart form data (images) or JSON
    v
FastAPI app (app/main.py)
    |-- /api/individuals   (admin: register / list / get / delete)
    |-- /api/identify      (public: single-frame recognition)
    |-- /static/*          (frontend assets)
    v
FaceEngine (app/core/face_engine.py)
    |-- Haar Cascade  -> face detection (bbox)
    |-- LBPH          -> face recognition (label + distance)
    v
SQLite via SQLAlchemy (app/models/db_models.py)
    |-- individuals    (profile fields shown on identification)
    |-- face_samples   (path to each stored, normalized face crop)
```

The frontend is deliberately plain HTML/CSS/JS rather than a build-tooled
framework - it's served directly as static files by the same FastAPI
process, which keeps the "run it locally" story to a single command and
avoids a Node build step for what is a handful of pages.

### Request flow: registration

1. Browser captures JPEG snapshots via `getUserMedia` + `<canvas>`.
2. `POST /api/individuals` (multipart: name/details + one or more images),
   guarded by the `X-Admin-Token` header.
3. Every image is validated to contain exactly one detectable face
   *before* anything is written to the database - a bad photo fails the
   whole request with a clear error rather than leaving a half-registered
   record.
4. Each accepted image is cropped to the face, normalized (grayscale,
   fixed size, histogram-equalized) and saved to
   `data/faces/<individual_id>/<uuid>.png`; a `FaceSample` row is created
   pointing at it.
5. The LBPH recognizer is retrained from every stored crop across all
   individuals so the new person becomes recognizable immediately.

### Request flow: identification

1. Browser grabs a frame from the live `<video>` element roughly every
   1.5 seconds and POSTs it to `/api/identify` (no auth - this is the
   walk-up-to-camera public flow).
2. The largest detected face is cropped/normalized the same way as
   registration and passed to `LBPHFaceRecognizer.predict()`, which
   returns the closest label and a distance score.
3. If the distance is under `LBPH_MAX_DISTANCE` (env-configurable,
   default 70), the match is accepted and that individual's profile is
   returned; otherwise the response reports "not identified." A missing
   face in the frame is reported distinctly from an unmatched face.
4. The endpoint always returns `200` with a structured `identified`
   boolean - "unrecognized" is a normal, expected outcome of this
   endpoint, not an error condition.

## Technology choices and justification

**Backend: FastAPI.** Async-capable, automatic request validation via
Pydantic, and free interactive API docs at `/docs` - useful both for
development and for anyone evaluating the API surface directly.

**Database: SQLite + SQLAlchemy.** The assignment's scale (a single
organization's registered individuals) doesn't call for a networked
database, and SQLite needs zero setup - it satisfies "must use a database
for persistent storage" without adding an external service to run
locally. SQLAlchemy's ORM keeps the schema declarative and queries
parameterized (no hand-built SQL, no injection surface). Swapping in
Postgres later is a one-line `DATABASE_URL` change since nothing else
touches SQL directly.

**Computer vision: Haar Cascade (detection) + LBPH (recognition), both
from OpenCV/opencv-contrib.** This was a deliberate choice after an
initial attempt to use a modern DNN pipeline (YuNet for detection, SFace
for embeddings) ran into the model weights being distributed via Git LFS
pointer files that this environment's network couldn't resolve - a
reminder that "free to select libraries" also means being accountable for
what's actually reliable to set up. Haar+LBPH ships *inside* the OpenCV
packages, so `pip install` is the entire setup step, with no model
download, no GPU, and no native build toolchain (dlib, by contrast, needs
cmake and a C++ compiler and is a common source of setup friction on a
fresh machine).

The trade-off is real: LBPH is a classical, texture-histogram-based
method and is measurably less robust to pose, expression and lighting
variation than a modern deep embedding model, and it must be **fully
retrained** (not incrementally updated) whenever the registered
population changes, since it can't remove a label in place. For a
small-to-medium roster in reasonably controlled lighting - the scope
implied by this assignment - retraining is fast (well under a second for
a few dozen people) and the accuracy trade-off is acceptable.

`FaceEngine` (`app/core/face_engine.py`) exposes a narrow interface -
`detect`, `preprocess`, `train`, `identify` - specifically so this
implementation could be swapped for a deep-embedding + cosine-similarity
approach (e.g. ArcFace/SFace, or a hosted API) later without changing any
calling code in the API layer. That would trade the zero-setup property
for materially better accuracy and O(1) add/remove instead of full
retrains - the right call for a larger or higher-stakes deployment.

**Frontend: plain HTML/CSS/JS.** No React/webpack build step; the
assignment asks for a browser-accessible frontend, not a specific
framework, and keeping it framework-free means `pip install && uvicorn`
is the entire local setup - no `npm install`, no build artifacts to
document.

## API reference

Interactive docs are available at `/docs` (Swagger UI) once the server is
running. Summary:

| Method | Path                       | Auth  | Purpose                                   |
|--------|----------------------------|-------|--------------------------------------------|
| POST   | `/api/individuals`         | admin | Register a new individual + face images    |
| GET    | `/api/individuals`         | admin | List all registered individuals            |
| GET    | `/api/individuals/{id}`    | admin | Get one individual                         |
| DELETE | `/api/individuals/{id}`    | admin | Remove an individual and retrain           |
| POST   | `/api/identify`            | none  | Identify a person from a single frame       |
| GET    | `/health`                  | none  | Liveness check                             |

## Security considerations

- **Authentication on write/read-PII paths.** Registration, roster
  listing, and deletion require a shared-secret `X-Admin-Token` header,
  checked with `secrets.compare_digest` to avoid timing side-channels.
  The identify endpoint is intentionally left open since it's the public
  walk-up flow the spec describes - it returns only the minimum profile
  fields needed for identification, nothing about the rest of the roster.
- **Rate limiting.** A lightweight in-memory per-IP limiter protects the
  unauthenticated `/api/identify` endpoint from being hammered.
- **Input validation.** Uploaded files are checked against an allowed
  MIME-type set and a size cap before decoding; malformed or oversized
  uploads are rejected with a clear 4xx rather than being processed.
- **No SQL injection surface.** All queries go through SQLAlchemy's ORM
  with bound parameters.
- **Fail-closed registration.** If any submitted photo doesn't contain a
  clearly detectable face, the entire registration is rejected before any
  database row or file is written - no partially-registered individuals.
- **Least-privilege data on identify.** The public identify response
  contains only the fields intended for display (name, role, contact,
  notes) - never raw face data or other individuals' records.
- **What a production hardening pass would add:** per-admin-user accounts
  (JWT/OAuth2) instead of one shared token, HTTPS termination in front of
  the app, encryption at rest for the face-image directory, and an audit
  log of registrations/deletions.

## Project structure

```
backend/
  app/
    main.py              FastAPI app, routes, startup hook
    api/
      individuals.py     Register / list / get / delete
      identify.py        Real-time identification endpoint
    core/
      config.py          Environment-driven settings
      database.py        SQLAlchemy engine/session
      security.py        Admin token dependency
      face_engine.py      Detection + LBPH recognition
      retrain.py          Retrain-from-DB helper
      rate_limit.py       Per-IP limiter for /api/identify
    models/
      db_models.py        SQLAlchemy ORM models
      schemas.py           Pydantic request/response schemas
  static/                  Frontend (HTML/CSS/JS), served by FastAPI
  data/                    SQLite DB + stored face crops (created at runtime)
  requirements.txt
  .env.example
```

## Known limitations

- LBPH accuracy is modest compared to deep embedding models, especially
  across large pose/lighting changes between registration and
  identification - see the CV justification above for the reasoning and
  the upgrade path.
- Retraining on every add/delete is O(all samples); fine at the scale
  this assignment implies, but would need to move to an incremental
  embedding-index approach (e.g. FAISS) for a large roster.
- The admin token is a single shared secret, appropriate for a small
  internal tool but not for multi-admin accountability - see the
  security section's hardening notes.
