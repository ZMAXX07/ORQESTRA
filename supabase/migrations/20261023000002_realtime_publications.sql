-- ==============================================================================
-- ORQESTRA DATABASE ARCHITECTURE: MIGRATION 20261023000002
-- Phase 4: Secure Realtime Publications and Replica Identity Configuration
-- ==============================================================================

-- 1. Ensure the supabase_realtime publication exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime'
  ) THEN
    CREATE PUBLICATION supabase_realtime;
  END IF;
END $$;

-- 2. Configure REPLICA IDENTITY FULL on subscribed operational tables
-- In Supabase Realtime, when rows are updated or deleted, PostgreSQL's default
-- replica identity only includes the primary key in the WAL event. Setting FULL
-- ensures the WAL contains all columns (specifically business_id), enabling
-- tenant filtering and Row Level Security evaluation on UPDATE and DELETE events.
ALTER TABLE public.products REPLICA IDENTITY FULL;
ALTER TABLE public.inventory REPLICA IDENTITY FULL;
ALTER TABLE public.orders REPLICA IDENTITY FULL;
ALTER TABLE public.stock_movements REPLICA IDENTITY FULL;

-- 3. Add operational tables to supabase_realtime publication idempotently
DO $$
BEGIN
  -- products
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables 
    WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = 'products'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.products;
  END IF;

  -- inventory
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables 
    WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = 'inventory'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.inventory;
  END IF;

  -- orders
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables 
    WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = 'orders'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.orders;
  END IF;

  -- stock_movements
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables 
    WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = 'stock_movements'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.stock_movements;
  END IF;
END $$;
