-- SmartWaste CM+ reference schema bootstrap.
-- This section makes a fresh PostGIS database usable before the historical seeds below.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'citoyen',
    arrondissement TEXT,
    language_preference TEXT NOT NULL DEFAULT 'fr',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    service_area VARCHAR(120),
    daily_capacity INTEGER NOT NULL DEFAULT 8,
    available_weekdays SMALLINT[] NOT NULL DEFAULT ARRAY[0,1,2,3,4,5,6],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (language_preference IN ('fr', 'en')),
    CHECK (daily_capacity > 0),
    CHECK (role IN ('citoyen', 'agent', 'ramasseur', 'gestionnaire', 'municipal', 'admin'))
);

CREATE TABLE IF NOT EXISTS tours (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER REFERENCES users(id),
    planned_date DATE,
    status TEXT NOT NULL DEFAULT 'planifiee',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    agent_id INTEGER REFERENCES users(id),
    tournee_id INTEGER REFERENCES tours(id),
    geometry GEOMETRY(Point, 4326) NOT NULL,
    severity TEXT NOT NULL DEFAULT 'en_analyse',
    confidence REAL,
    status TEXT NOT NULL DEFAULT 'soumis',
    photo_base64 TEXT,
    photo_preuve_base64 TEXT,
    resultat_preuve TEXT,
    confiance_preuve REAL,
    date_traitement TIMESTAMPTZ,
    waste_type TEXT,
    commentaire_gestion TEXT,
    report_count INTEGER NOT NULL DEFAULT 1,
    duplicate_group_id INTEGER,
    is_primary BOOLEAN NOT NULL DEFAULT TRUE,
    client_id UUID,
    description TEXT,
    address_text TEXT,
    classification_source VARCHAR(32),
    classification_model_version VARCHAR(100),
    analyzed_at TIMESTAMPTZ,
    human_review_required BOOLEAN NOT NULL DEFAULT FALSE,
    initial_severity VARCHAR(32),
    final_severity VARCHAR(32),
    reviewed_by INTEGER REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    review_reason TEXT,
    rejection_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_reports_user_client_id
    ON reports(user_id, client_id) WHERE client_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_agent_status ON reports(agent_id, status);
CREATE INDEX IF NOT EXISTS idx_reports_geometry ON reports USING GIST(geometry);

CREATE TABLE IF NOT EXISTS sorting_rules (
    id SERIAL PRIMARY KEY,
    keyword TEXT NOT NULL,
    waste_type TEXT NOT NULL,
    local_consigne TEXT,
    notes TEXT,
    aliases TEXT[] DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS zones (
    id SERIAL PRIMARY KEY,
    nom TEXT NOT NULL,
    zone_type TEXT,
    geometry GEOMETRY(Polygon, 4326)
);

CREATE TABLE IF NOT EXISTS chatbot_embeddings (
    id SERIAL PRIMARY KEY,
    type_dechet TEXT,
    reponse TEXT,
    conseil_pratique TEXT,
    detail_technique TEXT,
    impact_environnement TEXT,
    methode_valorisation TEXT,
    contact_douala TEXT
);

CREATE TABLE IF NOT EXISTS tournee_signalements (
    tournee_id INTEGER NOT NULL REFERENCES tours(id),
    report_id INTEGER NOT NULL REFERENCES reports(id),
    PRIMARY KEY (tournee_id, report_id)
);

CREATE TABLE IF NOT EXISTS agent_positions (
    agent_id INTEGER PRIMARY KEY REFERENCES users(id),
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS abonnements_collecte (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    adresse_geometry GEOMETRY(Point, 4326) NOT NULL,
    frequence TEXT NOT NULL,
    prochain_passage TIMESTAMPTZ,
    actif BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_id INTEGER REFERENCES users(id),
    actor_role VARCHAR(32) NOT NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id INTEGER,
    old_value JSONB,
    new_value JSONB,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS subscription_plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    frequency VARCHAR(32) NOT NULL CHECK (frequency IN ('hebdomadaire', 'bimensuelle', 'mensuelle')),
    price NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
    service_area VARCHAR(120),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS service_slots (
    id SERIAL PRIMARY KEY,
    service_area VARCHAR(120) NOT NULL,
    weekday SMALLINT NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    starts_at TIME NOT NULL,
    ends_at TIME NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 1 CHECK (capacity > 0),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (ends_at > starts_at)
);

CREATE TABLE IF NOT EXISTS domestic_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    plan_id INTEGER REFERENCES subscription_plans(id),
    address_geometry GEOMETRY(Point, 4326) NOT NULL,
    address_text TEXT,
    service_area VARCHAR(120),
    preferred_slot_id INTEGER REFERENCES service_slots(id),
    starts_on DATE NOT NULL DEFAULT CURRENT_DATE,
    ends_on DATE,
    status VARCHAR(32) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'cancelled')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (ends_on IS NULL OR ends_on >= starts_on)
);

CREATE TABLE IF NOT EXISTS collection_occurrences (
    id SERIAL PRIMARY KEY,
    subscription_id INTEGER NOT NULL REFERENCES domestic_subscriptions(id),
    collector_id INTEGER REFERENCES users(id),
    scheduled_for TIMESTAMPTZ NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'programmee'
        CHECK (status IN ('programmee', 'affectee', 'en_route', 'arrivee', 'effectuee', 'confirmee', 'manquee', 'reprogrammee', 'annulee')),
    missed_reason VARCHAR(64),
    rescheduled_to INTEGER REFERENCES collection_occurrences(id),
    started_at TIMESTAMPTZ,
    arrived_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (subscription_id, scheduled_for)
);

CREATE TABLE IF NOT EXISTS support_requests (
    id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES users(id),
    author_role VARCHAR(32) NOT NULL,
    category VARCHAR(64) NOT NULL CHECK (category IN ('collecte_manquee','comportement','erreur_affectation','adresse_inaccessible','danger','panne','preuve_contestee','probleme_technique','suggestion','autre')),
    subject VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    attachment_url TEXT,
    resource_type VARCHAR(32),
    resource_id INTEGER,
    priority VARCHAR(16) NOT NULL DEFAULT 'normal' CHECK (priority IN ('basse', 'normal', 'haute', 'critique')),
    status VARCHAR(32) NOT NULL DEFAULT 'ouverte'
        CHECK (status IN ('ouverte', 'en_examen', 'resolue', 'rejetee', 'fermee', 'contestee', 'remise_en_examen', 'soumise', 'reponse_envoyee', 'rouverte', 'cloturee')),
    assigned_to INTEGER REFERENCES users(id),
    manager_response TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    ,closed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    recipient_id INTEGER NOT NULL REFERENCES users(id),
    notification_type VARCHAR(64) NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    translation_key VARCHAR(120),
    translation_params JSONB DEFAULT '{}'::JSONB,
    link VARCHAR(2048),
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    resource_type VARCHAR(32),
    resource_id INTEGER,
    idempotency_key UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_recipient_idempotency
    ON notifications(recipient_id, idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS notification_delivery_outbox (
    notification_id BIGINT PRIMARY KEY REFERENCES notifications(id) ON DELETE CASCADE,
    recipient_id INTEGER NOT NULL REFERENCES users(id), attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error VARCHAR(500), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), delivered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_notification_outbox_pending
    ON notification_delivery_outbox(notification_id) WHERE delivered_at IS NULL;

CREATE TABLE IF NOT EXISTS conversations (
    id BIGSERIAL PRIMARY KEY, resource_type VARCHAR(32) NOT NULL CHECK (resource_type IN ('report','collection','tour','support')),
    resource_id INTEGER NOT NULL, created_by INTEGER NOT NULL REFERENCES users(id),
    status VARCHAR(16) NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), closed_at TIMESTAMPTZ, UNIQUE(resource_type,resource_id)
);
CREATE TABLE IF NOT EXISTS conversation_participants (
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id), joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY(conversation_id,user_id)
);
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY, conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id INTEGER REFERENCES users(id), client_id UUID NOT NULL,
    message_type VARCHAR(16) NOT NULL DEFAULT 'text' CHECK (message_type IN ('text','image','system')),
    body TEXT, attachment_base64 TEXT, attachment_mime VARCHAR(32), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (body IS NOT NULL OR attachment_base64 IS NOT NULL), UNIQUE(conversation_id,client_id)
);
CREATE TABLE IF NOT EXISTS conversation_reads (
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id), last_read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(conversation_id,user_id),
    FOREIGN KEY(conversation_id,user_id) REFERENCES conversation_participants(conversation_id,user_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS message_reports (
    id BIGSERIAL PRIMARY KEY, message_id BIGINT NOT NULL REFERENCES messages(id), reporter_id INTEGER NOT NULL REFERENCES users(id),
    reason VARCHAR(500) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(message_id,reporter_id)
);
CREATE TABLE IF NOT EXISTS callback_requests (
    id BIGSERIAL PRIMARY KEY, requester_id INTEGER NOT NULL REFERENCES users(id),
    resource_type VARCHAR(32) CHECK (resource_type IN ('report','collection','tour','support')), resource_id INTEGER,
    preferred_at TIMESTAMPTZ, reason VARCHAR(500) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'requested' CHECK (status IN ('requested','scheduled','completed','cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((resource_type IS NULL) = (resource_id IS NULL))
);

CREATE TABLE IF NOT EXISTS media_assets (
    id UUID PRIMARY KEY, storage_key VARCHAR(96) NOT NULL UNIQUE,
    uploader_id INTEGER NOT NULL REFERENCES users(id),
    purpose VARCHAR(40) NOT NULL CHECK (purpose IN ('report_initial','report_proof','collection_proof','dispute_photo','support_attachment','message_attachment')),
    resource_type VARCHAR(32), resource_id INTEGER,
    mime_type VARCHAR(32) NOT NULL CHECK (mime_type IN ('image/jpeg','image/png','image/webp')),
    extension VARCHAR(8) NOT NULL CHECK (extension IN ('.jpg','.png','.webp')),
    size_bytes INTEGER NOT NULL CHECK (size_bytes > 0), width INTEGER NOT NULL CHECK (width > 0), height INTEGER NOT NULL CHECK (height > 0),
    sha256 CHAR(64) NOT NULL, status VARCHAR(16) NOT NULL DEFAULT 'temporary' CHECK (status IN ('temporary','active','deleted','orphaned')),
    retention_until TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), deleted_at TIMESTAMPTZ,
    CHECK ((resource_type IS NULL) = (resource_id IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_media_resource ON media_assets(resource_type,resource_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_media_sha256 ON media_assets(sha256,mime_type,size_bytes);
CREATE INDEX IF NOT EXISTS idx_media_temporary ON media_assets(created_at) WHERE status='temporary';
ALTER TABLE reports ADD COLUMN IF NOT EXISTS initial_media_asset_id UUID REFERENCES media_assets(id);
ALTER TABLE reports ADD COLUMN IF NOT EXISTS proof_media_asset_id UUID REFERENCES media_assets(id);
ALTER TABLE messages ADD COLUMN IF NOT EXISTS media_asset_id UUID REFERENCES media_assets(id);
ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_check;
ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_content_check;
ALTER TABLE messages ADD CONSTRAINT messages_content_check CHECK (body IS NOT NULL OR attachment_base64 IS NOT NULL OR media_asset_id IS NOT NULL);
ALTER TABLE support_requests ADD COLUMN IF NOT EXISTS media_asset_id UUID REFERENCES media_assets(id);

CREATE INDEX IF NOT EXISTS idx_users_role_active ON users(role, active);
CREATE INDEX IF NOT EXISTS idx_abonnements_user_active ON abonnements_collecte(user_id, actif);
CREATE INDEX IF NOT EXISTS idx_reports_client_id ON reports(client_id);
CREATE INDEX IF NOT EXISTS idx_occurrences_collector_date ON collection_occurrences(collector_id, scheduled_for);
CREATE INDEX IF NOT EXISTS idx_occurrences_subscription_date ON collection_occurrences(subscription_id, scheduled_for);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(recipient_id, is_read, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_support_requests_author ON support_requests(author_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);

INSERT INTO sorting_rules (keyword, waste_type, local_consigne, notes, aliases)
VALUES
('pile', 'DEEE', 'Ne pas jeter à la poubelle ordinaire. Déposer dans un point de collecte DEEE ou signaler séparément.', 'Piles usagées, accumulateurs', ARRAY['piles', 'accus', 'batterie']),
('plastique', 'plastique', 'Revendre aux récupérateurs informels ou regrouper pour revente. Éviter de brûler.', 'Bouteilles, sachets, emballages', ARRAY['bouteille', 'sachet', 'bidon']),
('organique', 'organique', 'Compostage domestique ou dépôt dans un espace de compostage communautaire.', 'Restes de nourriture, épluchures', ARRAY['reste', 'nourriture', 'épluchure']);

SELECT * FROM sorting_rules;

SELECT id, severity,status, confidence, ST_AsText(geometry) AS point, created_at
FROM reports
ORDER BY id DESC
LIMIT 5;

SELECT id, nom, zone_type, 
       ST_GeometryType(geometry) AS type_geom,
       ST_Area(geometry::geography) / 1000000 AS superficie_km2
FROM zones
ORDER BY nom;

SELECT z.nom, COUNT(r.id) AS nb_signalements
FROM zones z
LEFT JOIN reports r ON ST_Contains(z.geometry, r.geometry)
GROUP BY z.nom
ORDER BY nb_signalements DESC;

SELECT id, severity, confidence, ST_AsText(geometry) AS point
FROM reports
ORDER BY id DESC;

ALTER TABLE reports DROP CONSTRAINT IF EXISTS reports_status_check;

ALTER TABLE reports ADD CONSTRAINT reports_status_check 
CHECK (status IN ('soumis', 'en_analyse', 'a_verifier', 'classifie', 'valide', 'rejete', 'hors_sujet', 'assigne', 'en_route', 'en_cours', 'traite', 'verification_requise', 'cloture', 'reouvert', 'refuse', 'rejete_hors_sujet', 'en_attente_validation'));

ALTER TABLE reports ADD COLUMN IF NOT EXISTS photo_base64 TEXT;

SELECT id, severity, 
       CASE 
           WHEN photo_base64 IS NULL THEN 'NULL' 
           WHEN length(photo_base64) > 100 THEN 'OK (' || length(photo_base64) || ' caractères)' 
           ELSE 'trop court' 
       END AS photo_status
FROM reports
ORDER BY id DESC;

SELECT id, severity, status,
       CASE 
           WHEN photo_base64 IS NULL THEN 'NULL' 
           ELSE 'OK (' || length(photo_base64) || ' caractères)' 
       END AS photo_status
FROM reports
ORDER BY id DESC
LIMIT 1;

SELECT id, severity, status, 
       CASE WHEN photo_base64 IS NULL THEN 'NULL' ELSE 'OK' END AS photo
FROM reports
ORDER BY id;

-- Vérifier la structure actuelle
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'users';

-- Ajouter la colonne password_hash si elle n'existe pas
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- Ajouter la colonne role si elle n'existe pas
ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'citoyen';

SELECT id, email, role, 
       LEFT(password_hash, 20) AS hash_prefix
FROM users;

-- Ajouter la colonne pour la photo de preuve
ALTER TABLE reports ADD COLUMN IF NOT EXISTS photo_preuve_base64 TEXT;

-- Ajouter la colonne pour le résultat de l'analyse
ALTER TABLE reports ADD COLUMN IF NOT EXISTS resultat_preuve TEXT;

-- Ajouter la colonne pour la confiance de l'analyse
ALTER TABLE reports ADD COLUMN IF NOT EXISTS confiance_preuve REAL;

-- Ajouter la colonne pour la date de traitement
ALTER TABLE reports ADD COLUMN IF NOT EXISTS date_traitement TIMESTAMPTZ;

-- Mettre à jour la contrainte de statut
ALTER TABLE reports DROP CONSTRAINT IF EXISTS reports_status_check;
ALTER TABLE reports ADD CONSTRAINT reports_status_check 
CHECK (status IN ('soumis', 'en_analyse', 'a_verifier', 'classifie', 'valide', 'rejete', 'hors_sujet', 'assigne', 'en_route', 'en_cours', 'traite', 'verification_requise', 'cloture', 'reouvert', 'refuse', 'rejete_hors_sujet', 'en_attente_validation'));

SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'reports' 
  AND column_name IN ('photo_preuve_base64', 'resultat_preuve', 'confiance_preuve', 'date_traitement');

SELECT id, severity, status, resultat_preuve, confiance_preuve,
       CASE 
           WHEN photo_preuve_base64 IS NULL THEN 'NULL' 
           ELSE 'OK' 
       END AS preuve
FROM reports
ORDER BY id;  

SELECT id, severity, status, 
       resultat_preuve, confiance_preuve,
       LEFT(photo_preuve_base64, 50) AS debut_preuve,
       date_traitement
FROM reports
WHERE id = 1;

-- Ajouter l'arrondissement à l'agent
ALTER TABLE users ADD COLUMN IF NOT EXISTS arrondissement TEXT;

-- Mettre à jour la contrainte de rôle pour inclure agent
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check 
CHECK (role IN ('citoyen', 'agent', 'ramasseur', 'gestionnaire', 'municipal', 'admin'));

-- Table des points d'embouteillage
CREATE TABLE IF NOT EXISTS embouteillages (
    id SERIAL PRIMARY KEY,
    geometry GEOMETRY(Point, 4326) NOT NULL,
    niveau TEXT NOT NULL DEFAULT 'moyen',
    CHECK (niveau IN ('faible', 'moyen', 'eleve', 'critique')),
    description TEXT,
    signale_par INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index spatial
CREATE INDEX IF NOT EXISTS idx_embouteillages_geometry ON embouteillages USING GIST (geometry);


-- Vérifier les colonnes de users
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'users' AND column_name = 'arrondissement';

-- Vérifier la table embouteillages
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'embouteillages';

-- Table des connaissances pour le chatbot
CREATE TABLE IF NOT EXISTS chatbot_knowledge (
    id SERIAL PRIMARY KEY,
    type_dechet TEXT NOT NULL,
    question TEXT,
    reponse TEXT NOT NULL,
    conseil_valorisation TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insérer les connaissances
INSERT INTO chatbot_knowledge (type_dechet, question, reponse, conseil_valorisation) VALUES
('plastique', 'Que faire avec une bouteille plastique ?', 
 'Les bouteilles plastiques peuvent être revendues aux récupérateurs informels à Douala. Elles sont recyclées pour fabriquer des fibres textiles, des tuyaux ou des objets en plastique.',
 'Rincez la bouteille, écrasez-la pour gagner de la place, et regroupez-les pour les revendre.'),

('plastique', 'Comment valoriser les sachets plastiques ?',
 'Les sachets plastiques peuvent être collectés et revendus. Certains artisans les utilisent pour fabriquer des sacs, des cordes ou des objets décoratifs.',
 'Ne les brûlez pas, c''est toxique. Regroupez-les et contactez un récupérateur.'),

('organique', 'Que faire avec les restes de nourriture ?',
 'Les restes de nourriture peuvent être compostés pour produire de l''engrais naturel. C''est idéal pour le jardinage urbain.',
 'Créez un petit composteur avec un bidon percé. Alternez couches de déchets verts et secs.'),

('organique', 'Comment composter chez soi ?',
 'Le compostage domestique est simple : il suffit d''un contenant aéré, d''alterner déchets humides et secs, et de retourner le mélange chaque semaine.',
 'Utilisez un vieux bidon ou un seau percé. Ajoutez des feuilles sèches ou du carton.'),

('DEEE', 'Que faire avec un téléphone cassé ?',
 'Les déchets électroniques contiennent des métaux précieux (or, cuivre). Ils doivent être déposés dans des points de collecte spécialisés.',
 'Ne les jetez pas à la poubelle. Cherchez un point de collecte DEEE près de chez vous.'),

('DEEE', 'Où déposer les piles usagées ?',
 'Les piles contiennent des métaux lourds toxiques. Elles doivent être déposées dans des points de collecte spécifiques.',
 'Gardez-les dans un bocal en verre et déposez-les dans un point de collecte.'),

('verre', 'Que faire avec les bouteilles en verre ?',
 'Le verre peut être recyclé à l''infini. Certains récupérateurs les rachètent pour les revendre aux brasseries.',
 'Rincez les bouteilles et regroupez-les pour la revente.'),

('metal', 'Que faire avec les canettes ?',
 'L''aluminium est très recherché par les récupérateurs. Les canettes peuvent être revendues facilement.',
 'Écrasez les canettes pour gagner de la place et regroupez-les.'),

('papier', 'Que faire avec les papiers et cartons ?',
 'Le papier et le carton peuvent être recyclés ou utilisés pour allumer le feu de manière contrôlée.',
 'Regroupez-les et vendez-les aux récupérateurs ou utilisez-les pour le compost.'),

('general', 'Comment réduire mes déchets ?',
 'Réduisez à la source : utilisez des sacs réutilisables, achetez en vrac, évitez les produits à usage unique.',
 'Commencez par refuser les sacs plastiques au marché et apportez votre propre sac.');

 -- Table des prix de référence par ville (source : stopblablacam, africatruth)
CREATE TABLE IF NOT EXISTS prix_reference (
    id SERIAL PRIMARY KEY,
    type_dechet TEXT NOT NULL,
    ville TEXT NOT NULL,
    prix_kg REAL NOT NULL,
    source TEXT,
    date_maj TIMESTAMPTZ DEFAULT NOW()
);

-- Insérer les données réelles
INSERT INTO prix_reference (type_dechet, ville, prix_kg, source) VALUES
('plastique', 'Douala', 75, 'EcoCollect - Prix officiels 2026'),
('plastique', 'Yaounde', 75, 'EcoCollect - Prix officiels 2026'),
('plastique', 'Bafoussam', 60, 'stopblablacam - Bafoussam recycling initiative'),
('aluminium', 'Douala', 200, 'EcoCollect - Prix officiels 2026'),
('aluminium', 'Yaounde', 200, 'EcoCollect - Prix officiels 2026'),
('ferraille', 'Douala', 100, 'EcoCollect - Prix officiels 2026'),
('ferraille', 'Yaounde', 100, 'EcoCollect - Prix officiels 2026'),
('papier', 'Douala', 50, 'EcoCollect - Prix officiels 2026'),
('papier', 'Yaounde', 50, 'EcoCollect - Prix officiels 2026'),
('verre', 'Douala', 50, 'EcoCollect - Prix officiels 2026'),
('verre', 'Yaounde', 50, 'EcoCollect - Prix officiels 2026');

-- Table des points de collecte agréés à Douala
CREATE TABLE IF NOT EXISTS points_collecte (
    id SERIAL PRIMARY KEY,
    nom TEXT NOT NULL,
    type_activite TEXT,
    contact TEXT,
    zone TEXT,
    arrondissement TEXT,
    geometry GEOMETRY(Point, 4326),
    types_dechets TEXT[] DEFAULT '{}',
    source TEXT
);

-- Insérer les points réels
INSERT INTO points_collecte (nom, type_activite, contact, zone, arrondissement, geometry, types_dechets, source) VALUES
('NAMé Recycling', 'Usine de traitement industriel', '+237 6 94 01 10 87', 'Zone industrielle', 'Douala', 
 ST_SetSRID(ST_MakePoint(9.7069, 4.0511), 4326), 
 ARRAY['plastique', 'PET', 'PEHD'], 'name-recycling.com'),

('EcoCollect Centre Principal', 'Centre de tri et rachat', NULL, 'Plusieurs points relais', 'Douala',
 ST_SetSRID(ST_MakePoint(9.7069, 4.0511), 4326),
 ARRAY['plastique', 'canette', 'ferraille'], 'ecocollect.cm'),

('Douala Clean City - Point Akwa', 'Point de tri sélectif', NULL, 'Akwa', 'Douala I',
 ST_SetSRID(ST_MakePoint(9.7069, 4.0511), 4326),
 ARRAY['plastique', 'verre', 'metal'], 'CUD'),

('Genelcam Centre', 'Collecte privée', NULL, 'Plusieurs arrondissements', 'Douala',
 ST_SetSRID(ST_MakePoint(9.6836, 4.0431), 4326),
 ARRAY['tout'], 'businessincameroon.com');


-- Créer la table des quartiers
CREATE TABLE IF NOT EXISTS quartiers_douala (
    id SERIAL PRIMARY KEY,
    nom_quartier TEXT NOT NULL,
    arrondissement TEXT NOT NULL,
    type_zone TEXT,
    geometry GEOMETRY(Point, 4326),
    source TEXT DEFAULT 'Enquête terrain + OSM'
);

-- Index spatial
CREATE INDEX IF NOT EXISTS idx_quartiers_geometry ON quartiers_douala USING GIST (geometry);

-- Mettre à jour la table quartiers_douala avec les coordonnées
TRUNCATE TABLE quartiers_douala;

-- Douala I
INSERT INTO quartiers_douala (nom_quartier, arrondissement, type_zone, geometry) VALUES
('Bonanjo', 'Douala I', 'Centre administratif', ST_SetSRID(ST_MakePoint(9.6836, 4.0431), 4326)),
('Bonapriso', 'Douala I', 'Résidentiel huppé', ST_SetSRID(ST_MakePoint(9.6911, 4.0321), 4326)),
('Akwa Nord', 'Douala I', 'Commercial', ST_SetSRID(ST_MakePoint(9.7069, 4.0511), 4326)),
('Joss', 'Douala I', 'Résidentiel', ST_SetSRID(ST_MakePoint(9.7001, 4.0461), 4326)),
('Deido', 'Douala I', 'Résidentiel', ST_SetSRID(ST_MakePoint(9.7071, 4.0631), 4326)),
('Bonamouti', 'Douala I', 'Commercial', ST_SetSRID(ST_MakePoint(9.7031, 4.0581), 4326)),
('Njo-Njo', 'Douala I', 'Résidentiel', ST_SetSRID(ST_MakePoint(9.6951, 4.0451), 4326)),
('Carrefour Idéal', 'Douala I', 'Commercial', ST_SetSRID(ST_MakePoint(9.6981, 4.0401), 4326));

-- Douala II
INSERT INTO quartiers_douala (nom_quartier, arrondissement, type_zone, geometry) VALUES
('New Bell', 'Douala II', 'Quartier populaire', ST_SetSRID(ST_MakePoint(9.7051, 4.0461), 4326)),
('Nkololoun', 'Douala II', 'Commercial', ST_SetSRID(ST_MakePoint(9.7101, 4.0431), 4326)),
('Congo', 'Douala II', 'Quartier populaire', ST_SetSRID(ST_MakePoint(9.7121, 4.0421), 4326)),
('Babylone', 'Douala II', 'Quartier populaire', ST_SetSRID(ST_MakePoint(9.7141, 4.0411), 4326)),
('Youpwé', 'Douala II', 'Zone côtière', ST_SetSRID(ST_MakePoint(9.7201, 4.0381), 4326)),
('Kassalafam', 'Douala II', 'Marchand', ST_SetSRID(ST_MakePoint(9.7081, 4.0441), 4326)),
('Lagos Market', 'Douala II', 'Marchand', ST_SetSRID(ST_MakePoint(9.7091, 4.0451), 4326));

-- Douala III
INSERT INTO quartiers_douala (nom_quartier, arrondissement, type_zone, geometry) VALUES
('Bassa', 'Douala III', 'Zone industrielle', ST_SetSRID(ST_MakePoint(9.7301, 4.0351), 4326)),
('Logbaba', 'Douala III', 'Résidentiel populaire', ST_SetSRID(ST_MakePoint(9.7301, 4.0451), 4326)),
('Ndogbati', 'Douala III', 'Résidentiel', ST_SetSRID(ST_MakePoint(9.7351, 4.0431), 4326)),
('Ndogpassi', 'Douala III', 'Extension urbaine', ST_SetSRID(ST_MakePoint(9.7351, 4.0401), 4326)),
('Nyala', 'Douala III', 'Extension urbaine', ST_SetSRID(ST_MakePoint(9.7401, 4.0381), 4326)),
('Japoma', 'Douala III', 'Périphérie', ST_SetSRID(ST_MakePoint(9.8301, 4.0151), 4326)),
('Nylon', 'Douala III', 'Forte densité', ST_SetSRID(ST_MakePoint(9.7201, 4.0501), 4326)),
('Tergal', 'Douala III', 'Populaire', ST_SetSRID(ST_MakePoint(9.7251, 4.0481), 4326)),
('Cité des Palmiers', 'Douala III', 'Classe moyenne', ST_SetSRID(ST_MakePoint(9.7401, 4.0551), 4326)),
('PK8', 'Douala III', 'Périphérie', ST_SetSRID(ST_MakePoint(9.7551, 4.0601), 4326)),
('PK14', 'Douala III', 'Périphérie', ST_SetSRID(ST_MakePoint(9.7601, 4.0651), 4326)),
('Logbessou', 'Douala III', 'Périphérie', ST_SetSRID(ST_MakePoint(9.7581, 4.0651), 4326)),
('Nkolbong', 'Douala III', 'Résidentiel', ST_SetSRID(ST_MakePoint(9.7381, 4.0521), 4326)),
('Brazzaville', 'Douala III', 'Résidentiel', ST_SetSRID(ST_MakePoint(9.7321, 4.0471), 4326));

-- Douala IV
INSERT INTO quartiers_douala (nom_quartier, arrondissement, type_zone, geometry) VALUES
('Bonassama', 'Douala IV', 'Mairie', ST_SetSRID(ST_MakePoint(9.6751, 4.0801), 4326)),
('Bonandale', 'Douala IV', 'Résidentiel', ST_SetSRID(ST_MakePoint(9.6801, 4.0781), 4326)),
('Sodiko', 'Douala IV', 'Résidentiel', ST_SetSRID(ST_MakePoint(9.6821, 4.0761), 4326)),
('Mambanda', 'Douala IV', 'Populaire', ST_SetSRID(ST_MakePoint(9.6701, 4.0821), 4326)),
('Grand Hangar', 'Douala IV', 'Populaire', ST_SetSRID(ST_MakePoint(9.6681, 4.0841), 4326)),
('Ndobo', 'Douala IV', 'Extension', ST_SetSRID(ST_MakePoint(9.6651, 4.0881), 4326)),
('Boongo', 'Douala IV', 'Extension', ST_SetSRID(ST_MakePoint(9.6621, 4.0901), 4326)),
('Quartier Bilingue', 'Douala IV', 'Mixte', ST_SetSRID(ST_MakePoint(9.6781, 4.0791), 4326)),
('Bonamatoumbe', 'Douala IV', 'Mixte', ST_SetSRID(ST_MakePoint(9.6761, 4.0811), 4326)),
('Bonaberi Rail', 'Douala IV', 'Mixte', ST_SetSRID(ST_MakePoint(9.6801, 4.0751), 4326)),
('PK10 Génie Militaire', 'Douala IV', 'Périphérie', ST_SetSRID(ST_MakePoint(9.6901, 4.0701), 4326)),
('PK20', 'Douala IV', 'Périphérie', ST_SetSRID(ST_MakePoint(9.7101, 4.0601), 4326)),
('Mobile Guinness', 'Douala IV', 'Périphérie', ST_SetSRID(ST_MakePoint(9.6851, 4.0721), 4326));

-- Douala V
INSERT INTO quartiers_douala (nom_quartier, arrondissement, type_zone, geometry) VALUES
('Bonamoussadi', 'Douala V', 'Résidentiel majeur', ST_SetSRID(ST_MakePoint(9.7501, 4.0801), 4326)),
('Makepe Missoke', 'Douala V', 'Résidentiel', ST_SetSRID(ST_MakePoint(9.7481, 4.0621), 4326)),
('Makepe BM', 'Douala V', 'Résidentiel', ST_SetSRID(ST_MakePoint(9.7451, 4.0611), 4326)),
('Logpom', 'Douala V', 'Classe moyenne', ST_SetSRID(ST_MakePoint(9.7501, 4.0851), 4326)),
('Bepanda', 'Douala V', 'Populaire', ST_SetSRID(ST_MakePoint(9.6911, 4.0321), 4326)),
('Cité SIC', 'Douala V', 'Étudiant', ST_SetSRID(ST_MakePoint(9.7421, 4.0581), 4326)),
('Université', 'Douala V', 'Étudiant', ST_SetSRID(ST_MakePoint(9.7401, 4.0561), 4326)),
('Yassa', 'Douala V', 'Périphérie', ST_SetSRID(ST_MakePoint(9.8261, 4.0271), 4326)),
('Kotto', 'Douala V', 'Résidentiel', ST_SetSRID(ST_MakePoint(9.7701, 4.0701), 4326)),
('Beedi', 'Douala V', 'Résidentiel', ST_SetSRID(ST_MakePoint(9.7701, 4.0751), 4326)),
('Lendi', 'Douala V', 'Résidentiel', ST_SetSRID(ST_MakePoint(9.7651, 4.0781), 4326)),
('Ndogbong', 'Douala V', 'Résidentiel', ST_SetSRID(ST_MakePoint(9.7661, 4.0531), 4326)),
('Malanguè', 'Douala V', 'Résidentiel', ST_SetSRID(ST_MakePoint(9.7681, 4.0681), 4326));

-- Douala VI
INSERT INTO quartiers_douala (nom_quartier, arrondissement, type_zone, geometry) VALUES
('Manoka', 'Douala VI', 'Île principale', ST_SetSRID(ST_MakePoint(9.5801, 3.9201), 4326)),
('Dahomey', 'Douala VI', 'Camp de pêcheurs', ST_SetSRID(ST_MakePoint(9.5701, 3.9301), 4326)),
('Cap Cameroun', 'Douala VI', 'Camp de pêcheurs', ST_SetSRID(ST_MakePoint(9.5901, 3.9101), 4326)),
('Bikoro', 'Douala VI', 'Village insulaire', ST_SetSRID(ST_MakePoint(9.5751, 3.9251), 4326));

SELECT arrondissement, COUNT(*) AS nb_quartiers
FROM quartiers_douala
GROUP BY arrondissement
ORDER BY arrondissement;

-- Ajouter les marchés principaux comme points de collecte par défaut
INSERT INTO points_collecte (nom, type_activite, zone, arrondissement, geometry, types_dechets, source) VALUES

-- Marchés Douala I
('Marché Central', 'Marché / Point de regroupement', 'Bonanjo', 'Douala I',
 ST_SetSRID(ST_MakePoint(9.6836, 4.0431), 4326), ARRAY['tout'], 'Marché principal'),
('Marché Deido', 'Marché / Point de regroupement', 'Deido', 'Douala I',
 ST_SetSRID(ST_MakePoint(9.7071, 4.0631), 4326), ARRAY['tout'], 'Marché principal'),

-- Marchés Douala II
('Marché New Bell', 'Marché / Point de regroupement', 'New Bell', 'Douala II',
 ST_SetSRID(ST_MakePoint(9.7051, 4.0461), 4326), ARRAY['tout'], 'Marché principal'),
('Marché Nkololoun', 'Marché / Point de regroupement', 'Nkololoun', 'Douala II',
 ST_SetSRID(ST_MakePoint(9.7101, 4.0431), 4326), ARRAY['tout'], 'Marché principal'),
('Marché Lagos', 'Marché / Point de regroupement', 'Lagos Market', 'Douala II',
 ST_SetSRID(ST_MakePoint(9.7091, 4.0451), 4326), ARRAY['tout'], 'Marché principal'),

-- Marchés Douala III
('Marché Bassa', 'Marché / Point de regroupement', 'Bassa', 'Douala III',
 ST_SetSRID(ST_MakePoint(9.7301, 4.0351), 4326), ARRAY['tout'], 'Marché principal'),
('Marché Ndogpassi', 'Marché / Point de regroupement', 'Ndogpassi', 'Douala III',
 ST_SetSRID(ST_MakePoint(9.7351, 4.0401), 4326), ARRAY['tout'], 'Marché principal'),
('Marché Cité des Palmiers', 'Marché / Point de regroupement', 'Cité des Palmiers', 'Douala III',
 ST_SetSRID(ST_MakePoint(9.7401, 4.0551), 4326), ARRAY['tout'], 'Marché principal'),
('Marché Japoma', 'Marché / Point de regroupement', 'Japoma', 'Douala III',
 ST_SetSRID(ST_MakePoint(9.8301, 4.0151), 4326), ARRAY['tout'], 'Marché principal'),

-- Marchés Douala IV
('Marché Bonabéri', 'Marché / Point de regroupement', 'Bonassama', 'Douala IV',
 ST_SetSRID(ST_MakePoint(9.6751, 4.0801), 4326), ARRAY['tout'], 'Marché principal'),
('Marché Grand Hangar', 'Marché / Point de regroupement', 'Grand Hangar', 'Douala IV',
 ST_SetSRID(ST_MakePoint(9.6681, 4.0841), 4326), ARRAY['tout'], 'Marché principal'),
('Marché Mambanda', 'Marché / Point de regroupement', 'Mambanda', 'Douala IV',
 ST_SetSRID(ST_MakePoint(9.6701, 4.0821), 4326), ARRAY['tout'], 'Marché principal'),
('Marché PK10', 'Marché / Point de regroupement', 'PK10 Génie Militaire', 'Douala IV',
 ST_SetSRID(ST_MakePoint(9.6901, 4.0701), 4326), ARRAY['tout'], 'Marché principal'),

-- Marchés Douala V
('Marché Bonamoussadi', 'Marché / Point de regroupement', 'Bonamoussadi', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.7501, 4.0801), 4326), ARRAY['tout'], 'Marché principal'),
('Marché Makepe', 'Marché / Point de regroupement', 'Makepe BM', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.7451, 4.0611), 4326), ARRAY['tout'], 'Marché principal'),
('Marché Logpom', 'Marché / Point de regroupement', 'Logpom', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.7501, 4.0851), 4326), ARRAY['tout'], 'Marché principal'),
('Marché Bepanda', 'Marché / Point de regroupement', 'Bepanda', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.6911, 4.0321), 4326), ARRAY['tout'], 'Marché principal'),
('Marché Kotto', 'Marché / Point de regroupement', 'Kotto', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.7701, 4.0701), 4326), ARRAY['tout'], 'Marché principal'),
('Marché Beedi', 'Marché / Point de regroupement', 'Beedi', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.7701, 4.0751), 4326), ARRAY['tout'], 'Marché principal'),
('Marché Yassa', 'Marché / Point de regroupement', 'Yassa', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.8261, 4.0271), 4326), ARRAY['tout'], 'Marché principal'),

-- Marchés Douala VI
('Marché Manoka', 'Marché / Point de regroupement', 'Manoka', 'Douala VI',
 ST_SetSRID(ST_MakePoint(9.5801, 3.9201), 4326), ARRAY['tout'], 'Marché principal');


 -- Ajouter la colonne fiabilite si elle n'existe pas
ALTER TABLE points_collecte ADD COLUMN IF NOT EXISTS fiabilite TEXT DEFAULT 'officiel';

-- Ajouter les marchés principaux
INSERT INTO points_collecte (nom, type_activite, zone, arrondissement, geometry, types_dechets, source, fiabilite) VALUES

-- Marchés Douala I
('Marché Central', 'Marché / Point de regroupement', 'Bonanjo', 'Douala I',
 ST_SetSRID(ST_MakePoint(9.6836, 4.0431), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Deido', 'Marché / Point de regroupement', 'Deido', 'Douala I',
 ST_SetSRID(ST_MakePoint(9.7071, 4.0631), 4326), ARRAY['tout'], 'Marché principal', 'marche'),

-- Marchés Douala II
('Marché New Bell', 'Marché / Point de regroupement', 'New Bell', 'Douala II',
 ST_SetSRID(ST_MakePoint(9.7051, 4.0461), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Nkololoun', 'Marché / Point de regroupement', 'Nkololoun', 'Douala II',
 ST_SetSRID(ST_MakePoint(9.7101, 4.0431), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Lagos', 'Marché / Point de regroupement', 'Lagos Market', 'Douala II',
 ST_SetSRID(ST_MakePoint(9.7091, 4.0451), 4326), ARRAY['tout'], 'Marché principal', 'marche'),

-- Marchés Douala III
('Marché Bassa', 'Marché / Point de regroupement', 'Bassa', 'Douala III',
 ST_SetSRID(ST_MakePoint(9.7301, 4.0351), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Ndogpassi', 'Marché / Point de regroupement', 'Ndogpassi', 'Douala III',
 ST_SetSRID(ST_MakePoint(9.7351, 4.0401), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Cité des Palmiers', 'Marché / Point de regroupement', 'Cité des Palmiers', 'Douala III',
 ST_SetSRID(ST_MakePoint(9.7401, 4.0551), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Japoma', 'Marché / Point de regroupement', 'Japoma', 'Douala III',
 ST_SetSRID(ST_MakePoint(9.8301, 4.0151), 4326), ARRAY['tout'], 'Marché principal', 'marche'),

-- Marchés Douala IV
('Marché Bonabéri', 'Marché / Point de regroupement', 'Bonassama', 'Douala IV',
 ST_SetSRID(ST_MakePoint(9.6751, 4.0801), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Grand Hangar', 'Marché / Point de regroupement', 'Grand Hangar', 'Douala IV',
 ST_SetSRID(ST_MakePoint(9.6681, 4.0841), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Mambanda', 'Marché / Point de regroupement', 'Mambanda', 'Douala IV',
 ST_SetSRID(ST_MakePoint(9.6701, 4.0821), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché PK10', 'Marché / Point de regroupement', 'PK10 Génie Militaire', 'Douala IV',
 ST_SetSRID(ST_MakePoint(9.6901, 4.0701), 4326), ARRAY['tout'], 'Marché principal', 'marche'),

-- Marchés Douala V
('Marché Bonamoussadi', 'Marché / Point de regroupement', 'Bonamoussadi', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.7501, 4.0801), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Makepe', 'Marché / Point de regroupement', 'Makepe BM', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.7451, 4.0611), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Logpom', 'Marché / Point de regroupement', 'Logpom', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.7501, 4.0851), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Bepanda', 'Marché / Point de regroupement', 'Bepanda', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.6911, 4.0321), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Kotto', 'Marché / Point de regroupement', 'Kotto', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.7701, 4.0701), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Beedi', 'Marché / Point de regroupement', 'Beedi', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.7701, 4.0751), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Yassa', 'Marché / Point de regroupement', 'Yassa', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.8261, 4.0271), 4326), ARRAY['tout'], 'Marché principal', 'marche'),

-- Marchés Douala VI
('Marché Manoka', 'Marché / Point de regroupement', 'Manoka', 'Douala VI',
 ST_SetSRID(ST_MakePoint(9.5801, 3.9201), 4326), ARRAY['tout'], 'Marché principal', 'marche');


 -- Générer un point par défaut pour chaque quartier sans point proche
INSERT INTO points_collecte (nom, zone, arrondissement, geometry, types_dechets, source, fiabilite)
SELECT 
    'Point de regroupement ' || q.nom_quartier,
    q.nom_quartier,
    q.arrondissement,
    q.geometry,
    ARRAY['tout'],
    'Point généré - densité',
    'genere'
FROM quartiers_douala q
WHERE NOT EXISTS (
    SELECT 1 FROM points_collecte p
    WHERE ST_Distance(p.geometry, q.geometry) < 0.005
);


-- Vérifier que chaque quartier a un point
SELECT q.nom_quartier, q.arrondissement,
       (SELECT COUNT(*) FROM points_collecte p 
        WHERE ST_Distance(p.geometry, q.geometry) < 0.005) AS nb_points_proches
FROM quartiers_douala q
ORDER BY nb_points_proches;

UPDATE points_collecte SET fiabilite = 'officiel' 
WHERE source LIKE '%NAMé%' OR source LIKE '%EcoCollect%' OR source LIKE '%Clean City%' OR source LIKE '%Genelcam%';

UPDATE points_collecte SET fiabilite = 'enquete' WHERE source LIKE '%Enquête%';
UPDATE points_collecte SET fiabilite = 'marche' WHERE source LIKE '%Marché%';
UPDATE points_collecte SET fiabilite = 'genere' WHERE source LIKE '%Point généré%';

SELECT id, nom, type_activite, 
       ST_Y(geometry) AS lat, ST_X(geometry) AS lon,
       source, fiabilite
FROM points_collecte
WHERE source = 'OSM';

-- Ajouter la colonne fiabilite si elle n'existe pas
ALTER TABLE points_collecte ADD COLUMN IF NOT EXISTS fiabilite TEXT DEFAULT 'officiel';

-- Ajouter les marchés principaux
INSERT INTO points_collecte (nom, type_activite, zone, arrondissement, geometry, types_dechets, source, fiabilite) VALUES

-- Marchés Douala I
('Marché Central', 'Marché / Point de regroupement', 'Bonanjo', 'Douala I',
 ST_SetSRID(ST_MakePoint(9.6836, 4.0431), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Deido', 'Marché / Point de regroupement', 'Deido', 'Douala I',
 ST_SetSRID(ST_MakePoint(9.7071, 4.0631), 4326), ARRAY['tout'], 'Marché principal', 'marche'),

-- Marchés Douala II
('Marché New Bell', 'Marché / Point de regroupement', 'New Bell', 'Douala II',
 ST_SetSRID(ST_MakePoint(9.7051, 4.0461), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Nkololoun', 'Marché / Point de regroupement', 'Nkololoun', 'Douala II',
 ST_SetSRID(ST_MakePoint(9.7101, 4.0431), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Lagos', 'Marché / Point de regroupement', 'Lagos Market', 'Douala II',
 ST_SetSRID(ST_MakePoint(9.7091, 4.0451), 4326), ARRAY['tout'], 'Marché principal', 'marche'),

-- Marchés Douala III
('Marché Bassa', 'Marché / Point de regroupement', 'Bassa', 'Douala III',
 ST_SetSRID(ST_MakePoint(9.7301, 4.0351), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Ndogpassi', 'Marché / Point de regroupement', 'Ndogpassi', 'Douala III',
 ST_SetSRID(ST_MakePoint(9.7351, 4.0401), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Cité des Palmiers', 'Marché / Point de regroupement', 'Cité des Palmiers', 'Douala III',
 ST_SetSRID(ST_MakePoint(9.7401, 4.0551), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Japoma', 'Marché / Point de regroupement', 'Japoma', 'Douala III',
 ST_SetSRID(ST_MakePoint(9.8301, 4.0151), 4326), ARRAY['tout'], 'Marché principal', 'marche'),

-- Marchés Douala IV
('Marché Bonabéri', 'Marché / Point de regroupement', 'Bonassama', 'Douala IV',
 ST_SetSRID(ST_MakePoint(9.6751, 4.0801), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Grand Hangar', 'Marché / Point de regroupement', 'Grand Hangar', 'Douala IV',
 ST_SetSRID(ST_MakePoint(9.6681, 4.0841), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Mambanda', 'Marché / Point de regroupement', 'Mambanda', 'Douala IV',
 ST_SetSRID(ST_MakePoint(9.6701, 4.0821), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché PK10', 'Marché / Point de regroupement', 'PK10 Génie Militaire', 'Douala IV',
 ST_SetSRID(ST_MakePoint(9.6901, 4.0701), 4326), ARRAY['tout'], 'Marché principal', 'marche'),

-- Marchés Douala V
('Marché Bonamoussadi', 'Marché / Point de regroupement', 'Bonamoussadi', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.7501, 4.0801), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Makepe', 'Marché / Point de regroupement', 'Makepe BM', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.7451, 4.0611), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Logpom', 'Marché / Point de regroupement', 'Logpom', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.7501, 4.0851), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Bepanda', 'Marché / Point de regroupement', 'Bepanda', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.6911, 4.0321), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Kotto', 'Marché / Point de regroupement', 'Kotto', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.7701, 4.0701), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Beedi', 'Marché / Point de regroupement', 'Beedi', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.7701, 4.0751), 4326), ARRAY['tout'], 'Marché principal', 'marche'),
('Marché Yassa', 'Marché / Point de regroupement', 'Yassa', 'Douala V',
 ST_SetSRID(ST_MakePoint(9.8261, 4.0271), 4326), ARRAY['tout'], 'Marché principal', 'marche'),

-- Marchés Douala VI
('Marché Manoka', 'Marché / Point de regroupement', 'Manoka', 'Douala VI',
 ST_SetSRID(ST_MakePoint(9.5801, 3.9201), 4326), ARRAY['tout'], 'Marché principal', 'marche');

 -- Générer un point par défaut pour chaque quartier sans point proche
INSERT INTO points_collecte (nom, zone, arrondissement, geometry, types_dechets, source, fiabilite)
SELECT 
    'Point de regroupement ' || q.nom_quartier,
    q.nom_quartier,
    q.arrondissement,
    q.geometry,
    ARRAY['tout'],
    'Point généré - densité',
    'genere'
FROM quartiers_douala q
WHERE NOT EXISTS (
    SELECT 1 FROM points_collecte p
    WHERE ST_Distance(p.geometry, q.geometry) < 0.005
);

SELECT 
    q.arrondissement,
    COUNT(DISTINCT q.nom_quartier) AS total_quartiers,
    COUNT(DISTINCT CASE WHEN p.id IS NOT NULL THEN q.nom_quartier END) AS quartiers_couverts
FROM quartiers_douala q
LEFT JOIN points_collecte p ON ST_Distance(p.geometry, q.geometry) < 0.005
GROUP BY q.arrondissement
ORDER BY q.arrondissement;

SELECT fiabilite, COUNT(*) AS nb_points
FROM points_collecte
GROUP BY fiabilite
ORDER BY nb_points DESC;

SELECT 
    q.arrondissement,
    COUNT(DISTINCT q.nom_quartier) AS total_quartiers,
    COUNT(DISTINCT CASE WHEN p.id IS NOT NULL THEN q.nom_quartier END) AS quartiers_couverts
FROM quartiers_douala q
LEFT JOIN points_collecte p ON ST_Distance(p.geometry, q.geometry) < 0.005
GROUP BY q.arrondissement
ORDER BY q.arrondissement;


-- Enrichir la table chatbot_knowledge
INSERT INTO chatbot_knowledge (type_dechet, question, reponse, conseil_valorisation) VALUES

('plastique', 'Que faire avec une bouteille plastique ?', 
 'Les bouteilles plastiques se revendent 75 FCFA/kg à Douala. Rincez-les, écrasez-les et regroupez-les.',
 'Revendez aux récupérateurs ou déposez dans un point EcoCollect.'),

('plastique', 'Comment gagner de l''argent avec le plastique ?',
 'Le plastique se revend 75 FCFA/kg. Regroupez au moins 10 kg pour une vente rentable.',
 'Stockez dans un sac, rincez et écrasez pour réduire le volume.'),

('aluminium', 'Que faire avec les canettes ?',
 'L''aluminium est très recherché : 200 FCFA/kg. C''est le déchet le plus rentable.',
 'Écrasez les canettes et regroupez-les pour la revente.'),

('verre', 'Que faire avec les bouteilles en verre ?',
 'Le verre se revend 50 FCFA/kg. Certaines brasseries les récupèrent.',
 'Rincez et regroupez par couleur si possible.'),

('papier', 'Que faire avec le carton ?',
 'Le carton se revend 50 FCFA/kg. Les récupérateurs l''acceptent facilement.',
 'Pliez à plat et gardez au sec.'),

('organique', 'Comment composter les restes de nourriture ?',
 'Les déchets organiques se compostent facilement. Utilisez un bidon percé.',
 'Alternez couches de déchets verts et secs. Retournez chaque semaine.'),

('batterie', 'Où jeter les piles usagées ?',
 'Les piles ne vont jamais à la poubelle ordinaire. Elles contiennent des métaux toxiques.',
 'Gardez dans un bocal en verre et déposez dans un point DEEE.');

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
        CREATE EXTENSION IF NOT EXISTS vector;
    ELSE
        RAISE NOTICE 'Extension vector indisponible: les fonctions pgvector restent désactivées';
    END IF;
END
$$;
