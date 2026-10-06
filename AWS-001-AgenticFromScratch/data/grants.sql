-- Read-only database role for the MCP server.
-- Enforcement layer: Kiro steering files guide what SQL gets written,
-- these grants decide what SQL can actually run.

CREATE ROLE mcp_reader;

GRANT USAGE  ON SCHEMA mcp                  TO ROLE mcp_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA mcp    TO ROLE mcp_reader;  -- includes views

-- The mcp views read rst tables, and Redshift needs USAGE on a schema a view reads from.
-- USAGE alone does not allow reading rst tables directly: there is no SELECT on schema rst,
-- so `SELECT * FROM rst.fact_orders` still fails with "permission denied for relation".
GRANT USAGE  ON SCHEMA rst                  TO ROLE mcp_reader;

-- No SELECT on schema rst. No INSERT/UPDATE/DELETE/DDL anywhere.

-- Mapping the ECS task role / AgentCore execution role to mcp_reader:
-- Redshift Serverless + Data API with IAM identity can map IAM principal tags to
-- database roles. Tag the IAM role:
--     RedshiftDbRoles = mcp_reader
-- Verify against current Redshift docs ("database roles for federated users")
-- during pre-event setup.

-- Guardrail on runaway queries: configure a query limit on the workgroup
-- (e.g. max_query_execution_time = 30 seconds) in addition to LIMIT in every tool.

-- Verify (run as admin):
-- SELECT * FROM svv_role_grants WHERE role_name = 'mcp_reader';
