-- ================================================================
-- Vehicle Service Shop — Schema DDL (PostgreSQL 14+)
-- Generated from vehicle_service_shop_schema.md
-- ================================================================
--
-- DESIGN DECISIONS (not specified in the source doc — flagging them):
--
-- 1. IDs: the source doc just says "string" for every id. Implemented as
--    UUID with gen_random_uuid() defaults, EXCEPT vehicle.vin, which is
--    used as a natural key (VINs are already globally unique 17-char
--    codes — no reason to wrap them in a surrogate key).
--
-- 2. Enums: implemented as VARCHAR + CHECK constraint, not native
--    Postgres ENUM types. A CHECK is a one-line ALTER to extend later;
--    a native enum requires ALTER TYPE ... ADD VALUE and has transaction
--    restrictions. If you're on MySQL/SQLite, these CHECKs port as-is
--    (SQLite enforces CHECK; MySQL 8.0.16+ does too).
--
-- 3. ON DELETE policy: RESTRICT by default everywhere. This is
--    financial/audit data (invoices, payments, work orders) — nothing
--    should silently cascade-delete. SET NULL is used only on genuinely
--    optional forward-pointers (e.g. quote.visit_id — a quote can exist
--    without ever having had a visit). If you want child rows
--    (line_item, po_line_item, diagnostic_finding) to cascade when
--    their parent is deleted, swap RESTRICT -> CASCADE on those specific
--    constraints.
--
-- 4. Circular FK (bay <-> work_order): bay.current_work_order_id is
--    created as a plain column with no constraint; the FK is added via
--    ALTER TABLE right after work_order is created, below.
--
-- 5. One-to-one(-or-zero) relationships from the doc's "Relationships at
--    a glance" table are enforced with UNIQUE, not left as convention:
--    work_order.quote_id, invoice.work_order_id, warranty.work_order_id,
--    change_order.finding_id.
--
-- Tables are created in dependency order — every FK target already
-- exists by the time it's referenced.
-- ================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto; -- for gen_random_uuid()

-- ================================================================
-- SECTION A — Independent root entities (no FKs)
-- ================================================================

CREATE TABLE customer (
    customer_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    customer_type   VARCHAR(20)  NOT NULL CHECK (customer_type IN ('individual', 'fleet')),
    billing_address VARCHAR(500),
    tax_exempt      BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE TABLE vendor (
    vendor_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    vendor_type VARCHAR(100)
);

CREATE TABLE technician (
    tech_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255)  NOT NULL,
    hourly_rate NUMERIC(10,2) NOT NULL CHECK (hourly_rate >= 0)
);

CREATE TABLE part (
    part_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part_number      VARCHAR(100) NOT NULL UNIQUE,
    category         VARCHAR(100),
    quantity_on_hand INTEGER      NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
    is_returnable    BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE payer (
    payer_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name           VARCHAR(255) NOT NULL,
    payer_type     VARCHAR(30)  NOT NULL CHECK (payer_type IN ('insurer', 'warranty_company', 'fleet_account')),
    contact_info   VARCHAR(500),
    billing_terms  VARCHAR(255),
    account_number VARCHAR(100)
);

-- current_work_order_id FK is added later, after work_order exists (see Section C)
CREATE TABLE bay (
    bay_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bay_type              VARCHAR(100),
    status                VARCHAR(20) NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'held', 'confirmed', 'occupied', 'cleaning', 'maintenance')),
    current_work_order_id UUID,
    held_until            TIMESTAMPTZ
);

-- ================================================================
-- SECTION B — First-level dependents
-- ================================================================

CREATE TABLE vehicle (
    vin             VARCHAR(17) PRIMARY KEY,
    customer_id     UUID NOT NULL REFERENCES customer(customer_id) ON DELETE RESTRICT,
    make            VARCHAR(100) NOT NULL,
    model           VARCHAR(100) NOT NULL,
    year            INTEGER NOT NULL CHECK (year BETWEEN 1900 AND 2100),
    current_mileage INTEGER CHECK (current_mileage >= 0)
);

CREATE TABLE certification (
    cert_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tech_id     UUID NOT NULL REFERENCES technician(tech_id) ON DELETE RESTRICT,
    cert_type   VARCHAR(100) NOT NULL,
    expiry_date DATE NOT NULL
);

-- ================================================================
-- SECTION C — Front-of-house workflow:
-- Appointment -> Visit -> Quote -> Work Order
-- ================================================================

CREATE TABLE appointment (
    appointment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id    UUID NOT NULL REFERENCES customer(customer_id) ON DELETE RESTRICT,
    vehicle_id     VARCHAR(17) NOT NULL REFERENCES vehicle(vin) ON DELETE RESTRICT,
    bay_id         UUID REFERENCES bay(bay_id) ON DELETE SET NULL,
    requested_date DATE NOT NULL,
    confirmed_date DATE,
    status         VARCHAR(20) NOT NULL DEFAULT 'requested'
        CHECK (status IN ('requested', 'confirmed', 'cancelled'))
);

-- Vehicle can be checked in & diagnosed before any quote/work order exists
CREATE TABLE visit (
    visit_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id     VARCHAR(17) NOT NULL REFERENCES vehicle(vin) ON DELETE RESTRICT,
    customer_id    UUID NOT NULL REFERENCES customer(customer_id) ON DELETE RESTRICT,
    appointment_id UUID REFERENCES appointment(appointment_id) ON DELETE SET NULL, -- null = walk-in
    checked_in_at  TIMESTAMPTZ NOT NULL,
    checked_out_at TIMESTAMPTZ,
    status         VARCHAR(20) NOT NULL DEFAULT 'checked_in'
        CHECK (status IN ('checked_in', 'in_diagnosis', 'awaiting_quote', 'in_service', 'awaiting_pickup', 'completed'))
);

CREATE TABLE quote (
    quote_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id     VARCHAR(17) NOT NULL REFERENCES vehicle(vin) ON DELETE RESTRICT,
    customer_id    UUID NOT NULL REFERENCES customer(customer_id) ON DELETE RESTRICT,
    visit_id       UUID REFERENCES visit(visit_id) ON DELETE SET NULL, -- null = remote/phone quote
    status         VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'issued', 'approved', 'declined', 'expired')),
    total_amount   NUMERIC(10,2) NOT NULL CHECK (total_amount >= 0),
    drafted_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    issued_at      TIMESTAMPTZ,
    valid_until    DATE NOT NULL,
    decline_reason VARCHAR(500)
);

CREATE TABLE work_order (
    work_order_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id          UUID NOT NULL UNIQUE REFERENCES quote(quote_id) ON DELETE RESTRICT, -- 1 quote -> 0/1 work order
    visit_id          UUID REFERENCES visit(visit_id) ON DELETE SET NULL,
    vehicle_id        VARCHAR(17) NOT NULL REFERENCES vehicle(vin) ON DELETE RESTRICT,
    customer_id       UUID NOT NULL REFERENCES customer(customer_id) ON DELETE RESTRICT,
    bay_id            UUID REFERENCES bay(bay_id) ON DELETE SET NULL,
    status            VARCHAR(20) NOT NULL DEFAULT 'created'
        CHECK (status IN ('created', 'scheduled', 'paused', 'active', 'closed', 'archived')),
    authorized_amount NUMERIC(10,2) NOT NULL CHECK (authorized_amount >= 0),
    promised_date     DATE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    scheduled_at      TIMESTAMPTZ,
    paused_at         TIMESTAMPTZ,
    pause_reason      VARCHAR(500),
    closed_at         TIMESTAMPTZ,
    archived_at       TIMESTAMPTZ
);

-- Resolving the circular FK: bay can now safely point at work_order
ALTER TABLE bay
    ADD CONSTRAINT fk_bay_current_work_order
    FOREIGN KEY (current_work_order_id) REFERENCES work_order(work_order_id) ON DELETE SET NULL;

-- ================================================================
-- SECTION D — Job execution
-- ================================================================

CREATE TABLE warranty (
    warranty_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_order_id UUID NOT NULL UNIQUE REFERENCES work_order(work_order_id) ON DELETE RESTRICT, -- 1 work order -> 0/1 warranty
    coverage_type VARCHAR(100),
    covers_labor  BOOLEAN NOT NULL DEFAULT FALSE,
    covers_parts  BOOLEAN NOT NULL DEFAULT FALSE,
    term          VARCHAR(100),
    start_date    DATE
);

CREATE TABLE line_item (
    line_item_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_order_id UUID NOT NULL REFERENCES work_order(work_order_id) ON DELETE RESTRICT,
    description   VARCHAR(500) NOT NULL,
    billing_mode  VARCHAR(20) NOT NULL CHECK (billing_mode IN ('flat_rate', 'hourly')),
    price         NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    status        VARCHAR(20) NOT NULL DEFAULT 'not_started'
        CHECK (status IN ('not_started', 'gated', 'in_progress', 'on_hold', 'completed')),
    hold_reason   VARCHAR(500),
    started_at    TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ
);

CREATE TABLE diagnostic (
    report_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    visit_id     UUID NOT NULL REFERENCES visit(visit_id) ON DELETE RESTRICT,
    vehicle_id   VARCHAR(17) NOT NULL REFERENCES vehicle(vin) ON DELETE RESTRICT,
    tech_id      UUID NOT NULL REFERENCES technician(tech_id) ON DELETE RESTRICT,
    performed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status       VARCHAR(20) NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'completed'))
);

CREATE TABLE diagnostic_finding (
    finding_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id   UUID NOT NULL REFERENCES diagnostic(report_id) ON DELETE RESTRICT,
    description VARCHAR(1000) NOT NULL
);

CREATE TABLE labor_entry (
    labor_entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tech_id        UUID NOT NULL REFERENCES technician(tech_id) ON DELETE RESTRICT,
    line_item_id   UUID NOT NULL REFERENCES line_item(line_item_id) ON DELETE RESTRICT,
    work_date      DATE NOT NULL,
    hours          NUMERIC(5,2) NOT NULL CHECK (hours > 0)
);

CREATE TABLE quality_check (
    qc_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    line_item_id UUID NOT NULL REFERENCES line_item(line_item_id) ON DELETE RESTRICT,
    tech_id      UUID NOT NULL REFERENCES technician(tech_id) ON DELETE RESTRICT,
    performed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status       VARCHAR(20) NOT NULL CHECK (status IN ('passed', 'failed'))
);

CREATE TABLE change_order (
    change_order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_order_id   UUID NOT NULL REFERENCES work_order(work_order_id) ON DELETE RESTRICT,
    line_item_id    UUID NOT NULL REFERENCES line_item(line_item_id) ON DELETE RESTRICT,
    finding_id      UUID UNIQUE REFERENCES diagnostic_finding(finding_id) ON DELETE SET NULL, -- 0/1 per finding
    reason          VARCHAR(500) NOT NULL,
    delta_amount    NUMERIC(10,2) NOT NULL,
    approval_status VARCHAR(20) NOT NULL DEFAULT 'issued'
        CHECK (approval_status IN ('issued', 'approved', 'declined')),
    approved_by     VARCHAR(255),
    approved_at     TIMESTAMPTZ,
    decline_reason  VARCHAR(500)
);

-- ================================================================
-- SECTION E — Parts & procurement
-- ================================================================

CREATE TABLE purchase_order (
    po_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id           UUID NOT NULL REFERENCES vendor(vendor_id) ON DELETE RESTRICT,
    status              VARCHAR(20) NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'confirmed', 'partially_shipped', 'complete', 'cancelled')),
    submitted_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at        TIMESTAMPTZ,
    expected_delivery   DATE,
    cancellation_reason VARCHAR(500)
);

CREATE TABLE po_line_item (
    po_line_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    po_id           UUID NOT NULL REFERENCES purchase_order(po_id) ON DELETE RESTRICT,
    part_id         UUID NOT NULL REFERENCES part(part_id) ON DELETE RESTRICT,
    qty_ordered     INTEGER NOT NULL CHECK (qty_ordered > 0),
    qty_shipped     INTEGER NOT NULL DEFAULT 0 CHECK (qty_shipped >= 0),
    qty_received    INTEGER NOT NULL DEFAULT 0 CHECK (qty_received >= 0)
);

CREATE TABLE part_instance (
    part_instance_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part_id              UUID NOT NULL REFERENCES part(part_id) ON DELETE RESTRICT,
    po_line_item_id      UUID REFERENCES po_line_item(po_line_item_id) ON DELETE SET NULL, -- null until ordered
    line_item_id         UUID REFERENCES line_item(line_item_id) ON DELETE SET NULL,        -- null until allocated
    serial_or_lot_number VARCHAR(100),
    status               VARCHAR(20) NOT NULL DEFAULT 'ordered'
        CHECK (status IN ('ordered', 'shipped', 'received', 'inspected', 'rejected', 'returned', 'installed')),
    received_at          TIMESTAMPTZ,
    inspected_at         TIMESTAMPTZ,
    rejection_reason     VARCHAR(500),
    installed_at         TIMESTAMPTZ
);

CREATE TABLE core (
    core_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part_id       UUID NOT NULL REFERENCES part(part_id) ON DELETE RESTRICT,
    charge_amount NUMERIC(10,2) NOT NULL CHECK (charge_amount >= 0),
    return_status VARCHAR(20) NOT NULL DEFAULT 'charged'
        CHECK (return_status IN ('charged', 'shipped', 'credited')),
    shipped_at    TIMESTAMPTZ
);

CREATE TABLE credit_memo (
    credit_memo_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    core_id          UUID REFERENCES core(core_id) ON DELETE RESTRICT,
    part_instance_id UUID REFERENCES part_instance(part_instance_id) ON DELETE RESTRICT,
    vendor_id        UUID NOT NULL REFERENCES vendor(vendor_id) ON DELETE RESTRICT,
    amount           NUMERIC(10,2) NOT NULL CHECK (amount >= 0),
    status           VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'issued')),
    issued_at        TIMESTAMPTZ,
    -- enforce "exactly one of core_id / part_instance_id is set" as a real constraint,
    -- not just a comment in the docs
    CONSTRAINT chk_credit_memo_exactly_one_source CHECK (
        (core_id IS NOT NULL AND part_instance_id IS NULL) OR
        (core_id IS NULL AND part_instance_id IS NOT NULL)
    )
);

-- ================================================================
-- SECTION F — Billing & warranty claims
-- ================================================================

CREATE TABLE invoice (
    invoice_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_order_id UUID NOT NULL UNIQUE REFERENCES work_order(work_order_id) ON DELETE RESTRICT, -- 1 work order -> 0/1 invoice
    customer_id   UUID NOT NULL REFERENCES customer(customer_id) ON DELETE RESTRICT,
    warranty_id   UUID REFERENCES warranty(warranty_id) ON DELETE SET NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'issued'
        CHECK (status IN ('issued', 'disputed', 'paid', 'voided', 'credited')),
    amount_due    NUMERIC(10,2) NOT NULL CHECK (amount_due >= 0),
    issued_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    credit_amount NUMERIC(10,2),
    credit_reason VARCHAR(500)
);

CREATE TABLE dispute (
    dispute_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id  UUID NOT NULL REFERENCES invoice(invoice_id) ON DELETE RESTRICT,
    opened_by   VARCHAR(20) NOT NULL CHECK (opened_by IN ('customer', 'shop')),
    reason      VARCHAR(500) NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'under_review', 'resolved')),
    opened_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    resolution  VARCHAR(1000)
);

CREATE TABLE payment (
    payment_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id   UUID NOT NULL REFERENCES invoice(invoice_id) ON DELETE RESTRICT,
    payer_id     UUID REFERENCES payer(payer_id) ON DELETE SET NULL, -- null = customer paid directly
    amount       NUMERIC(10,2) NOT NULL CHECK (amount > 0),
    method       VARCHAR(50) NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE deposit (
    deposit_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id      UUID NOT NULL REFERENCES quote(quote_id) ON DELETE RESTRICT,
    work_order_id UUID REFERENCES work_order(work_order_id) ON DELETE SET NULL,
    customer_id   UUID NOT NULL REFERENCES customer(customer_id) ON DELETE RESTRICT,
    amount        NUMERIC(10,2) NOT NULL CHECK (amount > 0),
    status        VARCHAR(20) NOT NULL DEFAULT 'collected'
        CHECK (status IN ('collected', 'applied', 'refunded')),
    collected_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    invoice_id    UUID REFERENCES invoice(invoice_id) ON DELETE SET NULL,
    refunded_at   TIMESTAMPTZ,
    refund_amount NUMERIC(10,2)
);

CREATE TABLE storage_charge (
    storage_charge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    visit_id          UUID NOT NULL REFERENCES visit(visit_id) ON DELETE RESTRICT,
    daily_rate        NUMERIC(10,2) NOT NULL CHECK (daily_rate >= 0),
    start_date        DATE NOT NULL,
    days_accrued      INTEGER NOT NULL DEFAULT 0 CHECK (days_accrued >= 0)
);

CREATE TABLE warranty_claim (
    claim_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    warranty_id UUID NOT NULL REFERENCES warranty(warranty_id) ON DELETE RESTRICT,
    claim_date  DATE NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'filed'
        CHECK (status IN ('filed', 'approved', 'denied', 'resolved')),
    resolution  VARCHAR(1000)
);

-- ================================================================
-- INDEXES — Postgres does NOT auto-index FK columns (only PKs/UNIQUEs).
-- Every FK column gets one, since these are the columns every JOIN
-- and lookup in this schema will filter or join on.
-- ================================================================

CREATE INDEX idx_vehicle_customer            ON vehicle(customer_id);
CREATE INDEX idx_certification_tech           ON certification(tech_id);

CREATE INDEX idx_appointment_customer         ON appointment(customer_id);
CREATE INDEX idx_appointment_vehicle          ON appointment(vehicle_id);
CREATE INDEX idx_appointment_bay              ON appointment(bay_id);

CREATE INDEX idx_visit_vehicle                ON visit(vehicle_id);
CREATE INDEX idx_visit_customer               ON visit(customer_id);
CREATE INDEX idx_visit_appointment            ON visit(appointment_id);

CREATE INDEX idx_quote_vehicle                ON quote(vehicle_id);
CREATE INDEX idx_quote_customer               ON quote(customer_id);
CREATE INDEX idx_quote_visit                  ON quote(visit_id);

CREATE INDEX idx_work_order_visit             ON work_order(visit_id);
CREATE INDEX idx_work_order_vehicle           ON work_order(vehicle_id);
CREATE INDEX idx_work_order_customer          ON work_order(customer_id);
CREATE INDEX idx_work_order_bay               ON work_order(bay_id);

CREATE INDEX idx_bay_current_work_order       ON bay(current_work_order_id);

CREATE INDEX idx_line_item_work_order         ON line_item(work_order_id);

CREATE INDEX idx_diagnostic_visit             ON diagnostic(visit_id);
CREATE INDEX idx_diagnostic_vehicle           ON diagnostic(vehicle_id);
CREATE INDEX idx_diagnostic_tech              ON diagnostic(tech_id);

CREATE INDEX idx_diagnostic_finding_report    ON diagnostic_finding(report_id);

CREATE INDEX idx_labor_entry_tech             ON labor_entry(tech_id);
CREATE INDEX idx_labor_entry_line_item        ON labor_entry(line_item_id);

CREATE INDEX idx_quality_check_line_item      ON quality_check(line_item_id);
CREATE INDEX idx_quality_check_tech           ON quality_check(tech_id);

CREATE INDEX idx_change_order_work_order      ON change_order(work_order_id);
CREATE INDEX idx_change_order_line_item       ON change_order(line_item_id);

CREATE INDEX idx_purchase_order_vendor        ON purchase_order(vendor_id);

CREATE INDEX idx_po_line_item_po              ON po_line_item(po_id);
CREATE INDEX idx_po_line_item_part            ON po_line_item(part_id);

CREATE INDEX idx_part_instance_part           ON part_instance(part_id);
CREATE INDEX idx_part_instance_po_line_item   ON part_instance(po_line_item_id);
CREATE INDEX idx_part_instance_line_item      ON part_instance(line_item_id);

CREATE INDEX idx_core_part                    ON core(part_id);

CREATE INDEX idx_credit_memo_core             ON credit_memo(core_id);
CREATE INDEX idx_credit_memo_part_instance    ON credit_memo(part_instance_id);
CREATE INDEX idx_credit_memo_vendor           ON credit_memo(vendor_id);

CREATE INDEX idx_invoice_customer             ON invoice(customer_id);
CREATE INDEX idx_invoice_warranty             ON invoice(warranty_id);

CREATE INDEX idx_dispute_invoice              ON dispute(invoice_id);

CREATE INDEX idx_payment_invoice              ON payment(invoice_id);
CREATE INDEX idx_payment_payer                ON payment(payer_id);

CREATE INDEX idx_deposit_quote                ON deposit(quote_id);
CREATE INDEX idx_deposit_work_order           ON deposit(work_order_id);
CREATE INDEX idx_deposit_customer             ON deposit(customer_id);
CREATE INDEX idx_deposit_invoice              ON deposit(invoice_id);

CREATE INDEX idx_storage_charge_visit         ON storage_charge(visit_id);

CREATE INDEX idx_warranty_claim_warranty      ON warranty_claim(warranty_id);

COMMIT;
