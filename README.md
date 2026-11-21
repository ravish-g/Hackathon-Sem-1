# Entropy · Crowd monitoring

Entropy estimates visible people in uploaded footage and network camera streams. A Django dashboard shows the latest sample for each feed. Calibrating a ground zone enables occupancy, people per square metre, density history and threshold alerts.

## Run the demonstration

Start Docker Desktop, then run from this checkout:

```powershell
docker compose -f deploy/docker-compose.yml up --build -d
docker compose -f deploy/docker-compose.yml ps
```

Open [the dashboard](http://localhost:8000/). PostgreSQL stores feeds, calibrations and observations. Docker volumes retain the database and uploaded videos across ordinary restarts.

1. Choose **Add feed → Video file** and upload an MP4. The player loops the upload and the vision worker publishes sampled counts.
2. For live input, choose **Network stream** and enter a direct HTTP, HTTPS or RTSP camera URL reachable from the vision container. For a service on the Windows presentation laptop, use `host.docker.internal` as the host. The live preview shows periodically refreshed camera frames. A worker camera index requires a device made available inside its container.
3. Open a feed to inspect its latest count, FPS and inference latency. Select **Calibrate zone** only when you know the real dimensions of a visible rectangle on the ground. Click its four corners in perimeter order and enter the two side lengths, starting with the side from corner one to corner two. The count then covers the selected zone.
4. Keep two feeds registered for continuous concurrent processing on the default configuration. Additional feeds share the two slots on rotation. The media player and the processing worker have independent playback clocks.

Use `docker compose -f deploy/docker-compose.yml logs --tail=40 vision` to inspect startup or source failures. Stop with `docker compose -f deploy/docker-compose.yml stop`. For the final round use this local Docker configuration on the presentation laptop.

## Verification

```powershell
python -m pip install -r requirements.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python -m pytest -q
```

The [benchmark notes](benchmarks/README.md) record the same-frame detector comparison and measured two-feed throughput. Count accuracy requires independently labeled footage. The [API contract](API_CONTRACT.md) describes the dashboard, worker and incident interfaces.

## Hosted deployment on a Linux VM

Use a Linux VM with Docker Engine, the current Compose plugin and persistent
disk. Point a DNS hostname to its public address. Allow inbound TCP 80 and
443 for Caddy and restrict SSH to the deployment administrator. Copy the
project checkout, including the model weights, to the VM. Run these commands
in the project root on a fresh deployment, replacing the example hostname.
Keep the generated environment file for subsequent updates.

```sh
umask 077
(test ! -e .env && {
  echo 'PUBLIC_HOST=crowd.example.org'
  for key in DJANGO_SECRET_KEY POSTGRES_PASSWORD WORKER_INGEST_TOKEN; do
    echo "$key=$(openssl rand -hex 32)"
  done
} > .env)
docker compose -f deploy/docker-compose.yml -f deploy/compose.hosted.yml up --build -d
docker compose -f deploy/docker-compose.yml -f deploy/compose.hosted.yml exec web python manage.py createsuperuser
```

Visit the HTTPS hostname and sign in. Upload the footage cleared for sharing.
New server volumes start empty. Network cameras must be reachable from the
remote worker. The hosted profile keeps database, Redis and worker ingest
inside the Docker network and requires sign-in for the dashboard and video
files. Dashboard users have operator controls. Back up the PostgreSQL and
media volumes before replacing the VM.
