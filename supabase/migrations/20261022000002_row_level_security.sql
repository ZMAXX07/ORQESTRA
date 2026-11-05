-- ==============================================================================
-- ORQESTRA DATABASE MIGRATION: Row Level Security & Authorization Policies
-- Migration: 20261022000002_row_level_security.sql
-- Description: Enables RLS, establishes non-recursive role policies, guards against
--              privilege escalation, enforces immutability, and establishes owner enrollment.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Security Definer Helper Functions (Prevents RLS Recursion)
-- ------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.get_auth_user_id()
RETURNS UUID AS $$
    SELECT coalesce(
        nullif(current_setting('request.jwt.claim.sub', true), ''),
        auth.uid()::text
    )::UUID;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION public.get_business_member_role(_business_id UUID, _user_id UUID)
RETURNS app_role
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
STABLE
AS $$
DECLARE
    _role app_role;
BEGIN
    IF _user_id IS NULL OR _business_id IS NULL THEN
        RETURN NULL;
    END IF;

    SELECT role INTO _role
    FROM business_members
    WHERE business_id = _business_id
      AND user_id = _user_id
      AND is_active = true;

    RETURN _role;
END;
$$;

CREATE OR REPLACE FUNCTION public.has_business_role(_business_id UUID, _user_id UUID, _required_role app_role)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
STABLE
AS $$
DECLARE
    _user_role app_role;
BEGIN
    _user_role := public.get_business_member_role(_business_id, _user_id);
    IF _user_role IS NULL THEN
        RETURN FALSE;
    END IF;

    IF _required_role = 'staff' THEN
        -- 'owner', 'admin', and 'staff' all satisfy 'staff' requirement
        RETURN TRUE;
    ELSIF _required_role = 'admin' THEN
        -- 'owner' and 'admin' satisfy 'admin' requirement
        RETURN _user_role IN ('owner', 'admin');
    ELSIF _required_role = 'owner' THEN
        -- only 'owner' satisfies 'owner' requirement
        RETURN _user_role = 'owner';
    END IF;

    RETURN FALSE;
END;
$$;

-- Restrict function execution permissions to authenticated callers
REVOKE EXECUTE ON FUNCTION public.get_auth_user_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_auth_user_id() TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.get_business_member_role(UUID, UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_business_member_role(UUID, UUID) TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.has_business_role(UUID, UUID, app_role) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.has_business_role(UUID, UUID, app_role) TO authenticated, service_role;

-- ------------------------------------------------------------------------------
-- 2. Business Creation Ownership Trigger
-- Automatically registers the creating user as the 'owner' in business_members.
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.handle_new_business()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF auth.uid() IS NOT NULL THEN
        INSERT INTO public.business_members (business_id, user_id, role, is_active)
        VALUES (NEW.id, auth.uid(), 'owner', true)
        ON CONFLICT (business_id, user_id) DO NOTHING;
    END IF;
    RETURN NEW;
END;
$$;

REVOKE EXECUTE ON FUNCTION public.handle_new_business() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.handle_new_business() TO authenticated, service_role;

DROP TRIGGER IF EXISTS trg_on_business_created ON businesses;
CREATE TRIGGER trg_on_business_created
    AFTER INSERT ON businesses
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_business();

-- ------------------------------------------------------------------------------
-- 3. Database-Level Immutability Enforcement for Audit Tables
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.prevent_immutable_modification()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RAISE EXCEPTION 'Table % is strictly immutable. UPDATE and DELETE operations are forbidden.', TG_TABLE_NAME;
END;
$$;

REVOKE EXECUTE ON FUNCTION public.prevent_immutable_modification() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.prevent_immutable_modification() TO authenticated, service_role;

DROP TRIGGER IF EXISTS trg_stock_movements_immutable ON stock_movements;
CREATE TRIGGER trg_stock_movements_immutable
    BEFORE UPDATE OR DELETE ON stock_movements
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_immutable_modification();

DROP TRIGGER IF EXISTS trg_audit_logs_immutable ON audit_logs;
CREATE TRIGGER trg_audit_logs_immutable
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_immutable_modification();

-- ------------------------------------------------------------------------------
-- 4. Enable RLS on All Core Tables
-- ------------------------------------------------------------------------------
ALTER TABLE businesses ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_movements ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- ------------------------------------------------------------------------------
-- 5. Policies: businesses
-- ------------------------------------------------------------------------------
CREATE POLICY "businesses_select_member"
    ON businesses FOR SELECT
    TO authenticated
    USING (public.has_business_role(id, auth.uid(), 'staff'));

CREATE POLICY "businesses_insert_authenticated"
    ON businesses FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "businesses_update_owner"
    ON businesses FOR UPDATE
    TO authenticated
    USING (public.has_business_role(id, auth.uid(), 'owner'))
    WITH CHECK (public.has_business_role(id, auth.uid(), 'owner'));

CREATE POLICY "businesses_delete_owner"
    ON businesses FOR DELETE
    TO authenticated
    USING (public.has_business_role(id, auth.uid(), 'owner'));

-- ------------------------------------------------------------------------------
-- 6. Policies: business_members
-- Anti-escalation: Admins can only invite 'staff'; only Owners can assign 'admin' or 'owner'.
-- ------------------------------------------------------------------------------
CREATE POLICY "business_members_select_colleagues"
    ON business_members FOR SELECT
    TO authenticated
    USING (
        user_id = auth.uid() OR
        public.has_business_role(business_id, auth.uid(), 'staff')
    );

CREATE POLICY "business_members_insert_authorized"
    ON business_members FOR INSERT
    TO authenticated
    WITH CHECK (
        -- Staff invitations can be performed by Admin or Owner
        (role = 'staff' AND public.has_business_role(business_id, auth.uid(), 'admin')) OR
        -- Admin or Owner role assignment strictly requires existing Owner
        (role IN ('admin', 'owner') AND public.has_business_role(business_id, auth.uid(), 'owner'))
    );

CREATE POLICY "business_members_update_owner"
    ON business_members FOR UPDATE
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'owner'))
    WITH CHECK (public.has_business_role(business_id, auth.uid(), 'owner'));

CREATE POLICY "business_members_delete_owner_or_self"
    ON business_members FOR DELETE
    TO authenticated
    USING (
        public.has_business_role(business_id, auth.uid(), 'owner') OR
        (user_id = auth.uid() AND role != 'owner')
    );

-- ------------------------------------------------------------------------------
-- 7. Policies: products
-- ------------------------------------------------------------------------------
CREATE POLICY "products_select_member"
    ON products FOR SELECT
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'staff'));

CREATE POLICY "products_insert_admin"
    ON products FOR INSERT
    TO authenticated
    WITH CHECK (public.has_business_role(business_id, auth.uid(), 'admin'));

CREATE POLICY "products_update_admin"
    ON products FOR UPDATE
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'admin'))
    WITH CHECK (public.has_business_role(business_id, auth.uid(), 'admin'));

CREATE POLICY "products_delete_owner"
    ON products FOR DELETE
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'owner'));

-- ------------------------------------------------------------------------------
-- 8. Policies: inventory
-- ------------------------------------------------------------------------------
CREATE POLICY "inventory_select_member"
    ON inventory FOR SELECT
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'staff'));

CREATE POLICY "inventory_insert_admin"
    ON inventory FOR INSERT
    TO authenticated
    WITH CHECK (public.has_business_role(business_id, auth.uid(), 'admin'));

CREATE POLICY "inventory_update_admin"
    ON inventory FOR UPDATE
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'admin'))
    WITH CHECK (public.has_business_role(business_id, auth.uid(), 'admin'));

CREATE POLICY "inventory_delete_owner"
    ON inventory FOR DELETE
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'owner'));

-- ------------------------------------------------------------------------------
-- 9. Policies: customers
-- ------------------------------------------------------------------------------
CREATE POLICY "customers_select_member"
    ON customers FOR SELECT
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'staff'));

CREATE POLICY "customers_insert_staff"
    ON customers FOR INSERT
    TO authenticated
    WITH CHECK (public.has_business_role(business_id, auth.uid(), 'staff'));

CREATE POLICY "customers_update_staff"
    ON customers FOR UPDATE
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'staff'))
    WITH CHECK (public.has_business_role(business_id, auth.uid(), 'staff'));

CREATE POLICY "customers_delete_admin"
    ON customers FOR DELETE
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'admin'));

-- ------------------------------------------------------------------------------
-- 10. Policies: orders
-- ------------------------------------------------------------------------------
CREATE POLICY "orders_select_member"
    ON orders FOR SELECT
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'staff'));

CREATE POLICY "orders_insert_staff"
    ON orders FOR INSERT
    TO authenticated
    WITH CHECK (public.has_business_role(business_id, auth.uid(), 'staff'));

CREATE POLICY "orders_update_staff"
    ON orders FOR UPDATE
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'staff'))
    WITH CHECK (public.has_business_role(business_id, auth.uid(), 'staff'));

CREATE POLICY "orders_delete_owner"
    ON orders FOR DELETE
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'owner'));

-- ------------------------------------------------------------------------------
-- 11. Policies: order_items
-- ------------------------------------------------------------------------------
CREATE POLICY "order_items_select_member"
    ON order_items FOR SELECT
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'staff'));

CREATE POLICY "order_items_insert_staff"
    ON order_items FOR INSERT
    TO authenticated
    WITH CHECK (public.has_business_role(business_id, auth.uid(), 'staff'));

CREATE POLICY "order_items_update_staff"
    ON order_items FOR UPDATE
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'staff'))
    WITH CHECK (public.has_business_role(business_id, auth.uid(), 'staff'));

CREATE POLICY "order_items_delete_admin"
    ON order_items FOR DELETE
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'admin'));

-- ------------------------------------------------------------------------------
-- 12. Policies: invoices
-- ------------------------------------------------------------------------------
CREATE POLICY "invoices_select_member"
    ON invoices FOR SELECT
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'staff'));

CREATE POLICY "invoices_insert_admin"
    ON invoices FOR INSERT
    TO authenticated
    WITH CHECK (public.has_business_role(business_id, auth.uid(), 'admin'));

CREATE POLICY "invoices_update_admin"
    ON invoices FOR UPDATE
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'admin'))
    WITH CHECK (public.has_business_role(business_id, auth.uid(), 'admin'));

CREATE POLICY "invoices_delete_owner"
    ON invoices FOR DELETE
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'owner'));

-- ------------------------------------------------------------------------------
-- 13. Policies: stock_movements (Append-only audit trail)
-- ------------------------------------------------------------------------------
CREATE POLICY "stock_movements_select_member"
    ON stock_movements FOR SELECT
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'staff'));

CREATE POLICY "stock_movements_insert_admin"
    ON stock_movements FOR INSERT
    TO authenticated
    WITH CHECK (public.has_business_role(business_id, auth.uid(), 'admin'));

-- No UPDATE or DELETE policies: strictly immutable via policy and trigger.

-- ------------------------------------------------------------------------------
-- 14. Policies: audit_logs (Append-only security log)
-- ------------------------------------------------------------------------------
CREATE POLICY "audit_logs_select_admin"
    ON audit_logs FOR SELECT
    TO authenticated
    USING (public.has_business_role(business_id, auth.uid(), 'admin'));

CREATE POLICY "audit_logs_insert_member"
    ON audit_logs FOR INSERT
    TO authenticated
    WITH CHECK (public.has_business_role(business_id, auth.uid(), 'staff'));

-- No UPDATE or DELETE policies: strictly immutable via policy and trigger.
