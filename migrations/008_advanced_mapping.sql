ALTER TABLE zones ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE zones ADD COLUMN IF NOT EXISTS arrondissement VARCHAR(120);
ALTER TABLE zones ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
DO $$ BEGIN ALTER TABLE zones ADD CONSTRAINT zones_geometry_valid CHECK (geometry IS NULL OR (ST_SRID(geometry)=4326 AND ST_IsValid(geometry))); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS idx_zones_geometry ON zones USING GIST(geometry);

ALTER TABLE tours ADD COLUMN IF NOT EXISTS collector_id INTEGER REFERENCES users(id);
ALTER TABLE tours ADD COLUMN IF NOT EXISTS zone_id INTEGER REFERENCES zones(id);
ALTER TABLE tours ADD COLUMN IF NOT EXISTS tour_type VARCHAR(20) NOT NULL DEFAULT 'report' CHECK(tour_type IN ('report','collection'));
ALTER TABLE tours ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1 CHECK(version>0);
ALTER TABLE tours ADD COLUMN IF NOT EXISTS routing_provider VARCHAR(32);
ALTER TABLE tours ADD COLUMN IF NOT EXISTS routing_status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK(routing_status IN ('pending','ready','unavailable','failed'));
ALTER TABLE tours ADD COLUMN IF NOT EXISTS route_geometry GEOMETRY(LineString,4326);
ALTER TABLE tours ADD COLUMN IF NOT EXISTS distance_m DOUBLE PRECISION CHECK(distance_m IS NULL OR distance_m>=0);
ALTER TABLE tours ADD COLUMN IF NOT EXISTS duration_s DOUBLE PRECISION CHECK(duration_s IS NULL OR duration_s>=0);
ALTER TABLE tours ADD COLUMN IF NOT EXISTS calculated_at TIMESTAMPTZ;
ALTER TABLE tours ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE tours ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
ALTER TABLE tours ADD COLUMN IF NOT EXISTS modification_reason VARCHAR(1000);
ALTER TABLE tours ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id);
CREATE INDEX IF NOT EXISTS idx_tours_collector_date ON tours(collector_id,planned_date,status);
CREATE INDEX IF NOT EXISTS idx_tours_route_geometry ON tours USING GIST(route_geometry);

CREATE TABLE IF NOT EXISTS tour_stops (
 id BIGSERIAL PRIMARY KEY,tour_id INTEGER NOT NULL REFERENCES tours(id),report_id INTEGER REFERENCES reports(id),
 occurrence_id INTEGER REFERENCES collection_occurrences(id),stop_order INTEGER NOT NULL CHECK(stop_order>0),
 status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','current','completed','missed','cancelled')),
 geometry GEOMETRY(Point,4326) NOT NULL,completed_at TIMESTAMPTZ,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CHECK((report_id IS NOT NULL)::int+(occurrence_id IS NOT NULL)::int=1),CHECK(ST_SRID(geometry)=4326),
 UNIQUE(tour_id,stop_order),UNIQUE(tour_id,report_id),UNIQUE(tour_id,occurrence_id)
);
CREATE INDEX IF NOT EXISTS idx_tour_stops_geometry ON tour_stops USING GIST(geometry);
CREATE INDEX IF NOT EXISTS idx_tour_stops_occurrence ON tour_stops(occurrence_id);

CREATE TABLE IF NOT EXISTS route_versions (
 id BIGSERIAL PRIMARY KEY,tour_id INTEGER NOT NULL REFERENCES tours(id),version INTEGER NOT NULL,
 provider VARCHAR(32),status VARCHAR(20) NOT NULL CHECK(status IN ('ready','unavailable','failed')),
 geometry GEOMETRY(LineString,4326),distance_m DOUBLE PRECISION,duration_s DOUBLE PRECISION,
 error_code VARCHAR(80),created_by INTEGER REFERENCES users(id),created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),UNIQUE(tour_id,version)
);

CREATE TABLE IF NOT EXISTS operational_positions (
 id BIGSERIAL PRIMARY KEY,tour_id INTEGER NOT NULL REFERENCES tours(id),actor_id INTEGER NOT NULL REFERENCES users(id),
 actor_role VARCHAR(20) NOT NULL CHECK(actor_role IN ('agent','ramasseur')),geometry GEOMETRY(Point,4326) NOT NULL,
 accuracy_m DOUBLE PRECISION NOT NULL CHECK(accuracy_m>=0 AND accuracy_m<=10000),source VARCHAR(20) NOT NULL DEFAULT 'device',
 recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),expires_at TIMESTAMPTZ NOT NULL,CHECK(ST_SRID(geometry)=4326),CHECK(expires_at>recorded_at)
);
CREATE INDEX IF NOT EXISTS idx_operational_positions_geometry ON operational_positions USING GIST(geometry);
CREATE INDEX IF NOT EXISTS idx_operational_positions_expiry ON operational_positions(expires_at);
CREATE INDEX IF NOT EXISTS idx_operational_positions_actor_time ON operational_positions(actor_id,recorded_at DESC);

CREATE TABLE IF NOT EXISTS tour_incidents (
 id BIGSERIAL PRIMARY KEY,tour_id INTEGER NOT NULL REFERENCES tours(id),stop_id BIGINT REFERENCES tour_stops(id),
 author_id INTEGER NOT NULL REFERENCES users(id),category VARCHAR(64) NOT NULL,description VARCHAR(2000) NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved')),created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),resolved_at TIMESTAMPTZ
);
