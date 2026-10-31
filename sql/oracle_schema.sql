-- GraphRAG-CodeAudit Oracle Autonomous AI Database schema (reference).
-- The local harness uses SQLite; this DDL mirrors the same logical model.

CREATE TABLE IF NOT EXISTS text_units (
  id VARCHAR2(4000) PRIMARY KEY,
  path VARCHAR2(4000) NOT NULL,
  start_line NUMBER NOT NULL,
  end_line NUMBER NOT NULL,
  text CLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
  id VARCHAR2(4000) PRIMARY KEY,
  name VARCHAR2(1000) NOT NULL,
  type VARCHAR2(128) NOT NULL,
  source_ids CLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS relationships (
  id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_id VARCHAR2(4000) NOT NULL,
  target_id VARCHAR2(4000) NOT NULL,
  type VARCHAR2(128) NOT NULL,
  weight BINARY_DOUBLE NOT NULL,
  source_ids CLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
  id VARCHAR2(4000) PRIMARY KEY,
  text CLOB NOT NULL,
  kind VARCHAR2(64) NOT NULL,
  entity_ids CLOB NOT NULL,
  source_ids CLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS communities (
  id VARCHAR2(128) PRIMARY KEY,
  level NUMBER NOT NULL,
  parent_id VARCHAR2(128),
  members CLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS community_reports (
  community_id VARCHAR2(128) PRIMARY KEY,
  level NUMBER NOT NULL,
  title VARCHAR2(1000) NOT NULL,
  summary CLOB NOT NULL,
  risks CLOB NOT NULL,
  dependencies CLOB NOT NULL,
  source_ids CLOB NOT NULL
);
