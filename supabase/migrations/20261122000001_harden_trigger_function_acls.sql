-- ==============================================================================
-- ORQESTRA DATABASE MIGRATION: Harden Trigger Function ACLs
-- Migration: 20261122000001_harden_trigger_function_acls.sql
-- Description: Revokes public and anon EXECUTE on set_updated_at_timestamp().
-- ==============================================================================

REVOKE EXECUTE ON FUNCTION public.set_updated_at_timestamp() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.set_updated_at_timestamp() FROM anon;
GRANT EXECUTE ON FUNCTION public.set_updated_at_timestamp() TO authenticated, service_role;
